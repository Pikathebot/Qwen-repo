import json
import logging
import math
import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Union
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from app.database.models import Memory
from app.memory.store import MemoryStore
from app.rag.embeddings import EmbeddingService
from app.agent.model_router import ModelRouter, TaskType

logger = logging.getLogger("jarvis.memory.manager")


class MemoryCategory(str, Enum):
    """
    Standardized memory categories conforming to Build Plan Section 6.
    """
    USER_PREFERENCE = "user_preference"
    PROJECT_PREFERENCE = "project_preference"
    RECURRING_FACT = "recurring_fact"
    WORKFLOW_PREFERENCE = "workflow_preference"
    IMPORTANT_DECISION = "important_decision"
    PERSISTENT_TASK_CONTEXT = "persistent_task_context"


class CandidateMemory(BaseModel):
    category: MemoryCategory
    content: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reason: str = Field(default="")


class MemoryCreate(BaseModel):
    category: MemoryCategory
    content: str = Field(..., min_length=1)
    project_id: Optional[str] = None
    source_session_id: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    pinned: bool = False


class MemoryUpdate(BaseModel):
    category: Optional[MemoryCategory] = None
    content: Optional[str] = None
    project_id: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    pinned: Optional[bool] = None


class MemoryRead(BaseModel):
    id: str
    project_id: Optional[str] = None
    category: str
    content: str
    source_session_id: Optional[str] = None
    confidence: float
    pinned: bool
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


class MemoryManager:
    """
    Long-Term Memory Manager for Project Nexus (Build Plan Section 6).
    Implements detection, semantic storage, CPU retrieval, updates, deletion,
    and vector-based deduplication.
    """

    def __init__(
        self,
        memory_store: Optional[MemoryStore] = None,
        embedding_service: Optional[EmbeddingService] = None,
        model_router: Optional[ModelRouter] = None,
    ):
        self.memory_store = memory_store or MemoryStore()
        self.embedding_service = embedding_service or EmbeddingService()
        self.model_router = model_router or ModelRouter()
        self._embedding_cache: dict[str, list[float]] = {}

    def _get_session(self) -> Session:
        return self.memory_store._get_session()

    def _get_memory_embedding(self, memory_id: str, content: str) -> list[float]:
        """Fetch cached embedding or compute via CPU EmbeddingService."""
        if memory_id in self._embedding_cache:
            return self._embedding_cache[memory_id]
        vec = self.embedding_service.embed_query(content)
        self._embedding_cache[memory_id] = vec
        return vec

    # -------------------------------------------------------------
    # 1. detect_candidate_memories
    # -------------------------------------------------------------
    def detect_candidate_memories(
        self,
        messages: list[dict[str, Any]]
    ) -> list[CandidateMemory]:
        """
        Extract high-value long-term memory candidates from conversation turns.
        Strictly avoids storing generic chit-chat or temporary statements.
        """
        candidates: list[CandidateMemory] = []
        if not messages:
            return candidates

        preference_patterns = [
            (re.compile(r"\b(?:i prefer|my preference is|always use|never use|prefer using|default to|my preferred)\s+([^.!?\n]+)", re.IGNORECASE), MemoryCategory.USER_PREFERENCE),
            (re.compile(r"\b(?:project standard|project rule|in this repo,?\s+always|code style for this project)\s+([^.!?\n]+)", re.IGNORECASE), MemoryCategory.PROJECT_PREFERENCE),
            (re.compile(r"\b(?:remember (?:that|this):?|key fact:?|note that|my (?:name|role|timezone|favorite language|email) is)\s+([^.!?\n]+)", re.IGNORECASE), MemoryCategory.RECURRING_FACT),
            (re.compile(r"\b(?:workflow rule:?|deployment convention|always run (?:pytest|tests|lint|build))\s+([^.!?\n]+)", re.IGNORECASE), MemoryCategory.WORKFLOW_PREFERENCE),
            (re.compile(r"\b(?:we decided to|decision:?|architectural decision:?|settled on)\s+([^.!?\n]+)", re.IGNORECASE), MemoryCategory.IMPORTANT_DECISION),
            (re.compile(r"\b(?:persistent task:?|open action item:?|todo for later:?|pending task:?)\s+([^.!?\n]+)", re.IGNORECASE), MemoryCategory.PERSISTENT_TASK_CONTEXT),
        ]

        seen_content = set()

        for msg in messages:
            content = (msg.get("content") or "").strip()
            role = msg.get("role", "").lower()
            if not content or len(content) < 8:
                continue

            # Skip common conversational noise
            noise_greetings = {"hello", "hi", "hey", "thanks", "thank you", "ok", "okay", "got it", "good morning"}
            if content.lower() in noise_greetings:
                continue

            # Run pattern matching
            for pattern, cat in preference_patterns:
                match = pattern.search(content)
                if match:
                    extracted = match.group(0).strip()
                    if extracted.lower() not in seen_content:
                        seen_content.add(extracted.lower())
                        candidates.append(CandidateMemory(
                            category=cat,
                            content=extracted,
                            confidence=0.95,
                            reason=f"Matched high-value pattern for {cat.value}"
                        ))

            # Explicit prefix check
            if content.lower().startswith("remember:") or content.lower().startswith("memory:"):
                raw_mem = re.sub(r"^(?:remember|memory):\s*", "", content, flags=re.IGNORECASE).strip()
                if raw_mem and raw_mem.lower() not in seen_content:
                    seen_content.add(raw_mem.lower())
                    candidates.append(CandidateMemory(
                        category=MemoryCategory.RECURRING_FACT,
                        content=raw_mem,
                        confidence=1.0,
                        reason="Explicit memory tag prefix"
                    ))

        return candidates

    # -------------------------------------------------------------
    # 2. store_memory
    # -------------------------------------------------------------
    def store_memory(self, memory: MemoryCreate) -> Memory:
        """
        Store a validated memory record in the database and index CPU embedding.
        """
        now = datetime.utcnow()
        cat_val = memory.category.value if isinstance(memory.category, MemoryCategory) else str(memory.category)
        mem_id = str(uuid.uuid4())

        mem_obj = Memory(
            id=mem_id,
            project_id=memory.project_id,
            category=cat_val,
            content=memory.content.strip(),
            source_session_id=memory.source_session_id,
            confidence=memory.confidence,
            pinned=memory.pinned,
            created_at=now,
            updated_at=now,
            last_used_at=None,
        )

        with self._get_session() as session:
            try:
                session.add(mem_obj)
                session.commit()
                session.refresh(mem_obj)
            except Exception:
                session.rollback()
                raise

        # Pre-compute and cache CPU vector embedding
        self._get_memory_embedding(mem_id, mem_obj.content)
        logger.info("Stored memory [%s]: category='%s', len=%d chars", mem_id, cat_val, len(mem_obj.content))
        return mem_obj

    # -------------------------------------------------------------
    # 3. retrieve_memories
    # -------------------------------------------------------------
    def retrieve_memories(
        self,
        query: str,
        limit: int = 5,
        project_id: Optional[str] = None,
        category: Optional[Union[MemoryCategory, str]] = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve relevant memories using CPU-only semantic search + cosine similarity.
        """
        cat_str = category.value if isinstance(category, MemoryCategory) else category

        with self._get_session() as session:
            stmt = select(Memory)
            if project_id:
                stmt = stmt.where((Memory.project_id == project_id) | (Memory.project_id.is_(None)))
            if cat_str:
                stmt = stmt.where(Memory.category == cat_str)
            all_memories = session.exec(stmt).all()

        if not all_memories:
            return []

        # If empty query, return most recently updated / pinned memories
        if not query.strip():
            sorted_mem = sorted(
                all_memories,
                key=lambda m: (1 if m.pinned else 0, m.updated_at.timestamp() if m.updated_at else 0),
                reverse=True
            )
            return [
                {
                    "id": m.id,
                    "project_id": m.project_id,
                    "category": m.category,
                    "content": m.content,
                    "confidence": m.confidence,
                    "pinned": m.pinned,
                    "score": 1.0 if m.pinned else 0.5,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "updated_at": m.updated_at.isoformat() if m.updated_at else None,
                }
                for m in sorted_mem[:limit]
            ]

        # Generate query vector on CPU
        query_vec = self.embedding_service.embed_query(query)

        scored: list[dict[str, Any]] = []
        now_ts = datetime.utcnow().timestamp()

        for m in all_memories:
            m_vec = self._get_memory_embedding(m.id, m.content)
            sim = cosine_similarity(query_vec, m_vec)

            # Lexical boost for exact word matches
            q_words = set(re.findall(r"\w+", query.lower()))
            m_words = set(re.findall(r"\w+", m.content.lower()))
            overlap = len(q_words.intersection(m_words))
            lexical_boost = min(0.4, overlap * 0.1)

            # Subtle pinned boost for tie-breaking
            pinned_boost = 0.05 if m.pinned else 0.0

            final_score = round(sim + lexical_boost + pinned_boost, 4)

            scored.append({
                "id": m.id,
                "project_id": m.project_id,
                "category": m.category,
                "content": m.content,
                "confidence": m.confidence,
                "pinned": m.pinned,
                "score": final_score,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        results = scored[:limit]

        # Touch last_used_at on top retrieved memories
        with self._get_session() as session:
            try:
                for r in results:
                    mem_record = session.get(Memory, r["id"])
                    if mem_record:
                        mem_record.last_used_at = datetime.utcnow()
                        session.add(mem_record)
                session.commit()
            except Exception:
                session.rollback()

        return results

    # -------------------------------------------------------------
    # 4. update_memory
    # -------------------------------------------------------------
    def update_memory(
        self,
        memory_id: str,
        updates: Union[dict[str, Any], MemoryUpdate]
    ) -> Memory:
        """
        Update fields of an existing memory and refresh embeddings if content changed.
        """
        update_dict = updates.model_dump(exclude_unset=True) if isinstance(updates, MemoryUpdate) else updates

        with self._get_session() as session:
            try:
                mem = session.get(Memory, memory_id)
                if not mem:
                    raise KeyError(f"Memory with ID '{memory_id}' not found.")

                content_changed = False
                for k, v in update_dict.items():
                    if v is not None and hasattr(mem, k):
                        if k == "category" and isinstance(v, MemoryCategory):
                            v = v.value
                        if k == "content" and v != mem.content:
                            content_changed = True
                        setattr(mem, k, v)

                mem.updated_at = datetime.utcnow()
                session.add(mem)
                session.commit()
                session.refresh(mem)

                # Invalidate cache if content changed
                if content_changed:
                    self._embedding_cache.pop(memory_id, None)
                    self._get_memory_embedding(memory_id, mem.content)

                return mem
            except Exception:
                session.rollback()
                raise

    # -------------------------------------------------------------
    # 5. delete_memory
    # -------------------------------------------------------------
    def delete_memory(self, memory_id: str) -> bool:
        """
        Delete memory record by ID.
        """
        with self._get_session() as session:
            try:
                mem = session.get(Memory, memory_id)
                if not mem:
                    return False
                session.delete(mem)
                session.commit()
                self._embedding_cache.pop(memory_id, None)
                return True
            except Exception:
                session.rollback()
                raise

    # -------------------------------------------------------------
    # 6. deduplicate_memories
    # -------------------------------------------------------------
    def deduplicate_memories(
        self,
        project_id: Optional[str] = None,
        similarity_threshold: float = 0.88,
    ) -> int:
        """
        Identifies and removes duplicate or redundant memories using CPU vector similarity.
        Retains higher confidence / pinned / newer memories. Returns count of deleted duplicates.
        """
        with self._get_session() as session:
            stmt = select(Memory)
            if project_id:
                stmt = stmt.where(Memory.project_id == project_id)
            memories = session.exec(stmt).all()

        if len(memories) < 2:
            return 0

        # Sort memories so highest priority stays first: pinned > confidence > newer
        sorted_mems = sorted(
            memories,
            key=lambda m: (
                1 if m.pinned else 0,
                m.confidence,
                m.updated_at.timestamp() if m.updated_at else 0
            ),
            reverse=True
        )

        to_delete_ids: set[str] = set()

        for i in range(len(sorted_mems)):
            mem_a = sorted_mems[i]
            if mem_a.id in to_delete_ids:
                continue

            vec_a = self._get_memory_embedding(mem_a.id, mem_a.content)

            for j in range(i + 1, len(sorted_mems)):
                mem_b = sorted_mems[j]
                if mem_b.id in to_delete_ids:
                    continue

                # Same category or general preference check
                if mem_a.category == mem_b.category or mem_a.content.strip().lower() == mem_b.content.strip().lower():
                    vec_b = self._get_memory_embedding(mem_b.id, mem_b.content)
                    sim = cosine_similarity(vec_a, vec_b)

                    # Exact content match or high cosine similarity
                    if sim >= similarity_threshold or mem_a.content.strip().lower() == mem_b.content.strip().lower():
                        logger.info(
                            "Deduplicating memory '%s' (sim=%.3f with keeper '%s')",
                            mem_b.id, sim, mem_a.id
                        )
                        to_delete_ids.add(mem_b.id)

        # Delete marked duplicates
        if to_delete_ids:
            with self._get_session() as session:
                try:
                    for del_id in to_delete_ids:
                        m_obj = session.get(Memory, del_id)
                        if m_obj:
                            session.delete(m_obj)
                            self._embedding_cache.pop(del_id, None)
                    session.commit()
                except Exception:
                    session.rollback()
                    raise

        logger.info("Deduplication completed: purged %d duplicate memories", len(to_delete_ids))
        return len(to_delete_ids)
