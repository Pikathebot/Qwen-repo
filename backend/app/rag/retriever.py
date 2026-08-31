import logging
from typing import Any, Optional

from app.config import settings
from app.rag.embeddings import EmbeddingService, RerankerService
from app.rag.vector_store import VectorStoreService
from app.rag.keyword_store import KeywordSearchService

logger = logging.getLogger("jarvis.rag.retriever")


def reciprocal_rank_fusion(
    ranked_lists: list[list[dict[str, Any]]],
    k: int = 60
) -> list[dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) algorithm.
    Combines multiple ranked candidate lists into a single unified ranking.
    RRF_score(d) = sum_m( 1 / (k + rank_m(d)) )
    """
    scores: dict[str, float] = {}
    doc_map: dict[str, dict[str, Any]] = {}

    for ranked_list in ranked_lists:
        for rank, doc in enumerate(ranked_list, start=1):
            doc_id = doc.get("chunk_id") or doc.get("id")
            if not doc_id:
                continue

            if doc_id not in doc_map:
                doc_map[doc_id] = dict(doc)

            # Accumulate RRF score
            rrf_delta = 1.0 / (k + rank)
            scores[doc_id] = scores.get(doc_id, 0.0) + rrf_delta

    # Sort merged results by RRF score descending
    sorted_doc_ids = sorted(scores.keys(), key=lambda d_id: scores[d_id], reverse=True)

    fused_results = []
    for rank, doc_id in enumerate(sorted_doc_ids, start=1):
        doc = doc_map[doc_id]
        doc["rrf_score"] = round(scores[doc_id], 6)
        doc["rrf_rank"] = rank
        fused_results.append(doc)

    return fused_results


class HybridRetriever:
    """
    Hybrid Retrieval Engine complying with Build Plan Section 9.
    Orchestrates Semantic Vector Search (Qdrant), Exact Keyword/Symbol Search (FTS5),
    Reciprocal Rank Fusion (RRF), and CPU-Only Cross-Encoder Reranking.
    """

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        vector_store: Optional[VectorStoreService] = None,
        keyword_store: Optional[KeywordSearchService] = None,
        reranker: Optional[RerankerService] = None
    ):
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStoreService(embedding_service=self.embedding_service)
        self.keyword_store = keyword_store or KeywordSearchService()
        self.reranker = reranker or RerankerService()

    def retrieve(
        self,
        project_id: str,
        query: str,
        top_k: int = 5,
        semantic_limit: int = 20,
        keyword_limit: int = 20,
        filters: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """
        Execute full hybrid retrieval pipeline:
        1. Embed user query on CPU.
        2. Semantic vector search (top 20 from Qdrant).
        3. Lexical exact keyword/symbol search (top 20 from SQLite FTS5).
        4. Reciprocal Rank Fusion (merge to top 40 candidates).
        5. CPU Reranking (top 5 final chunks with Section 8 metadata).
        """
        if not query or not query.strip():
            return []

        # 1. Semantic search
        try:
            query_vector = self.embedding_service.embed_query(query)
            semantic_results = self.vector_store.search_semantic(
                project_id=project_id,
                query_vector=query_vector,
                top_k=semantic_limit,
                filters=filters
            )
        except Exception as e:
            logger.warning("Semantic search failed for project %s: %s", project_id, e)
            semantic_results = []

        # 2. Keyword exact search
        try:
            keyword_results = self.keyword_store.search_keyword(
                project_id=project_id,
                query=query,
                top_k=keyword_limit
            )
        except Exception as e:
            logger.warning("Keyword search failed for project %s: %s", project_id, e)
            keyword_results = []

        # 3. Reciprocal Rank Fusion (RRF)
        fused_candidates = reciprocal_rank_fusion(
            [semantic_results, keyword_results],
            k=60
        )

        if not fused_candidates:
            logger.debug("No hybrid search candidates found for query: %s", query)
            return []

        # Take up to 40 candidates for CPU reranking
        rerank_candidates = fused_candidates[:40]

        # 4. CPU-Only Reranking
        final_chunks = self.reranker.rerank(
            query=query,
            docs=rerank_candidates,
            top_k=top_k
        )

        logger.info(
            "Hybrid retrieval complete for project %s: %d semantic, %d keyword -> %d RRF -> %d final reranked chunks",
            project_id,
            len(semantic_results),
            len(keyword_results),
            len(fused_candidates),
            len(final_chunks)
        )
        return final_chunks
