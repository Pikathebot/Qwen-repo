import json
import logging
import os
import sqlite3
import time
from typing import Any, Optional

logger = logging.getLogger("jarvis.memory.store")


class MemoryStore:
    """
    SQLite-backed short-term conversation memory and compaction event store.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_dir()
        self._init_db()

    def _ensure_dir(self) -> None:
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at REAL,
                    updated_at REAL
                )
            """)

            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT,
                    name TEXT,
                    tool_calls_json TEXT,
                    token_estimate INTEGER DEFAULT 0,
                    is_summary INTEGER DEFAULT 0,
                    created_at REAL,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages (session_id, id)
            """)

            # Compaction events audit table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS compaction_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    tokens_before INTEGER NOT NULL,
                    tokens_after INTEGER NOT NULL,
                    details TEXT,
                    created_at REAL,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
                )
            """)
            conn.commit()

    def get_or_create_session(self, session_id: str, title: Optional[str] = None) -> dict[str, Any]:
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)

            default_title = title or f"Session {session_id[:8]}"
            cursor.execute("""
                INSERT INTO sessions (session_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            """, (session_id, default_title, now, now))
            conn.commit()
            return {
                "session_id": session_id,
                "title": default_title,
                "created_at": now,
                "updated_at": now
            }

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions ORDER BY updated_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def delete_session(self, session_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM compaction_events WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content, name, tool_calls_json, is_summary
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
            """, (session_id,))
            rows = cursor.fetchall()
            
            messages = []
            for row in rows:
                msg: dict[str, Any] = {
                    "role": row["role"],
                    "content": row["content"] or ""
                }
                if row["name"]:
                    msg["name"] = row["name"]
                if row["tool_calls_json"]:
                    try:
                        msg["tool_calls"] = json.loads(row["tool_calls_json"])
                    except Exception:
                        pass
                if row["is_summary"]:
                    msg["is_summary"] = bool(row["is_summary"])
                messages.append(msg)
            return messages

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        name: Optional[str] = None,
        tool_calls: Optional[list] = None,
        is_summary: bool = False
    ) -> None:
        self.get_or_create_session(session_id)
        now = time.time()
        tool_calls_str = json.dumps(tool_calls) if tool_calls else None
        token_estimate = max(1, len(content or "") // 4)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (session_id, role, content, name, tool_calls_json, token_estimate, is_summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, role, content, name, tool_calls_str, token_estimate, 1 if is_summary else 0, now))
            
            cursor.execute("""
                UPDATE sessions SET updated_at = ? WHERE session_id = ?
            """, (now, session_id))
            conn.commit()

    def replace_messages(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        """
        Replace all stored messages for a session (used after compaction).
        """
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                name = msg.get("name")
                tool_calls = msg.get("tool_calls")
                tool_calls_str = json.dumps(tool_calls) if tool_calls else None
                is_summary = 1 if msg.get("is_summary") else 0
                token_est = max(1, len(content) // 4)
                
                cursor.execute("""
                    INSERT INTO messages (session_id, role, content, name, tool_calls_json, token_estimate, is_summary, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (session_id, role, content, name, tool_calls_str, token_est, is_summary, now))
            
            cursor.execute("""
                UPDATE sessions SET updated_at = ? WHERE session_id = ?
            """, (now, session_id))
            conn.commit()

    def record_compaction(
        self,
        session_id: str,
        strategy: str,
        tokens_before: int,
        tokens_after: int,
        details: Optional[str] = None
    ) -> dict[str, Any]:
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO compaction_events (session_id, strategy, tokens_before, tokens_after, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, strategy, tokens_before, tokens_after, details, now))
            conn.commit()
            return {
                "session_id": session_id,
                "strategy": strategy,
                "tokens_before": tokens_before,
                "tokens_after": tokens_after,
                "details": details,
                "timestamp": now
            }

    def get_compaction_events(self, session_id: str) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM compaction_events WHERE session_id = ? ORDER BY id ASC
            """, (session_id,))
            return [dict(row) for row in cursor.fetchall()]
