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
                    chat_mode TEXT DEFAULT 'WORKSPACE',
                    created_at REAL,
                    updated_at REAL
                )
            """)
            try:
                cursor.execute("ALTER TABLE sessions ADD COLUMN chat_mode TEXT DEFAULT 'WORKSPACE'")
            except sqlite3.OperationalError:
                pass


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

            # Tool call audit table (Stage A & B)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tool_call_audit (
                    call_id TEXT PRIMARY KEY,
                    turn_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    tool_name TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    model_tier TEXT NOT NULL,
                    validation_result TEXT NOT NULL,
                    permission_result TEXT NOT NULL,
                    executed INTEGER NOT NULL,
                    error TEXT,
                    repair_attempt INTEGER NOT NULL DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tool_audit_turn ON tool_call_audit (turn_id, timestamp)
            """)
            cursor.execute("PRAGMA table_info(tool_call_audit)")
            existing_cols = [col[1] for col in cursor.fetchall()]
            if existing_cols and "repair_attempt" not in existing_cols:
                cursor.execute("ALTER TABLE tool_call_audit ADD COLUMN repair_attempt INTEGER NOT NULL DEFAULT 0")

            # Reliability & Rollback events audit table (Stage B Addendum)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reliability_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    backend_from TEXT NOT NULL,
                    backend_to TEXT NOT NULL,
                    reliability_rate REAL NOT NULL,
                    window_size INTEGER NOT NULL,
                    failed_calls_count INTEGER NOT NULL,
                    failed_calls_json TEXT NOT NULL,
                    details TEXT
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rel_events_ts ON reliability_events (timestamp DESC)
            """)
            conn.commit()


    def get_or_create_session(
        self,
        session_id: str,
        title: Optional[str] = None,
        chat_mode: Optional[str] = "WORKSPACE"
    ) -> dict[str, Any]:
        now = time.time()
        mode_val = (chat_mode or "WORKSPACE").upper()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                session_dict = dict(row)
                if chat_mode and session_dict.get("chat_mode") != mode_val:
                    cursor.execute("UPDATE sessions SET chat_mode = ?, updated_at = ? WHERE session_id = ?", (mode_val, now, session_id))
                    conn.commit()
                    session_dict["chat_mode"] = mode_val
                return session_dict

            default_title = title or f"Session {session_id[:8]}"
            cursor.execute("""
                INSERT INTO sessions (session_id, title, chat_mode, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, default_title, mode_val, now, now))
            conn.commit()
            return {
                "session_id": session_id,
                "title": default_title,
                "chat_mode": mode_val,
                "created_at": now,
                "updated_at": now
            }

    def set_session_chat_mode(self, session_id: str, chat_mode: str) -> None:
        mode_val = (chat_mode or "WORKSPACE").upper()
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE sessions SET chat_mode = ?, updated_at = ? WHERE session_id = ?", (mode_val, now, session_id))
            conn.commit()


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

    def record_tool_call_audit(
        self,
        call_id: str,
        turn_id: str,
        tool_name: str,
        args: dict[str, Any],
        model_tier: str,
        validation_result: str,
        permission_result: str,
        executed: bool,
        error: Optional[str] = None,
        timestamp: Optional[float] = None,
        repair_attempt: int = 0,
    ) -> dict[str, Any]:
        now = timestamp if timestamp is not None else time.time()
        args_json = json.dumps(args, sort_keys=True) if isinstance(args, dict) else str(args)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO tool_call_audit (
                    call_id, turn_id, timestamp, tool_name, args_json,
                    model_tier, validation_result, permission_result, executed, error, repair_attempt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                call_id, turn_id, now, tool_name, args_json,
                model_tier, validation_result, permission_result, 1 if executed else 0, error, repair_attempt
            ))
            conn.commit()
            return {
                "call_id": call_id,
                "turn_id": turn_id,
                "timestamp": now,
                "tool_name": tool_name,
                "args_json": args_json,
                "model_tier": model_tier,
                "validation_result": validation_result,
                "permission_result": permission_result,
                "executed": executed,
                "error": error,
                "repair_attempt": repair_attempt,
            }

    def get_tool_call_audits(
        self,
        turn_id: Optional[str] = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if turn_id:
                cursor.execute("""
                    SELECT * FROM tool_call_audit
                    WHERE turn_id = ?
                    ORDER BY timestamp ASC
                    LIMIT ?
                """, (turn_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM tool_call_audit
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_tool_call_stats(self, model_tier: Optional[str] = None) -> dict[str, Any]:
        """
        Compute empirical tool-calling reliability metrics:
        First-attempt valid rate, repaired valid rate, and escalation rate.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if model_tier:
                cursor.execute("SELECT validation_result, repair_attempt, executed FROM tool_call_audit WHERE model_tier = ?", (model_tier,))
            else:
                cursor.execute("SELECT validation_result, repair_attempt, executed FROM tool_call_audit")
            rows = cursor.fetchall()

        total = len(rows)
        if total == 0:
            return {
                "total_calls": 0,
                "first_attempt_valid_count": 0,
                "first_attempt_valid_rate": 1.0,
                "repaired_valid_count": 0,
                "repaired_valid_rate": 0.0,
                "escalated_count": 0,
                "escalated_rate": 0.0,
                "executed_count": 0,
            }

        first_attempt_valid = sum(1 for r in rows if r["validation_result"] == "valid" and r["repair_attempt"] == 0)
        repaired_valid = sum(1 for r in rows if r["validation_result"] == "valid" and r["repair_attempt"] > 0)
        escalated = sum(1 for r in rows if r["validation_result"] == "invalid_escalated")
        executed = sum(1 for r in rows if r["executed"] == 1)

        return {
            "total_calls": total,
            "first_attempt_valid_count": first_attempt_valid,
            "first_attempt_valid_rate": round(first_attempt_valid / total, 4),
            "repaired_valid_count": repaired_valid,
            "repaired_valid_rate": round(repaired_valid / total, 4),
            "escalated_count": escalated,
            "escalated_rate": round(escalated / total, 4),
            "executed_count": executed,
        }

    def calculate_rolling_reliability(
        self,
        window_size: int = 30,
        model_tier: Optional[str] = "tier2",
        floor: float = 0.75,
        since_timestamp: Optional[float] = None
    ) -> dict[str, Any]:
        """
        Calculates tool-call reliability over a rolling window of the most recent tool calls.
        Formula: (first-attempt clean calls + auto-repaired calls) / total tool calls.
        A call counts as success if valid on first attempt OR auto-repaired.
        A call counts as failure if attempted, failed, and could not be repaired.
        Cold-start guard: returns cold_start=True if total_samples < window_size.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            conditions = ["validation_result != 'invalid_repaired'"]
            params = []
            if model_tier:
                conditions.append("model_tier = ?")
                params.append(model_tier)
            if since_timestamp is not None:
                conditions.append("timestamp >= ?")
                params.append(since_timestamp)
            
            where_clause = " AND ".join(conditions)
            params.append(window_size)
            query = f"""
                SELECT call_id, turn_id, timestamp, tool_name, args_json,
                       model_tier, validation_result, permission_result, executed, error, repair_attempt
                FROM tool_call_audit
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
            """
            cursor.execute(query, tuple(params))
            rows = [dict(r) for r in cursor.fetchall()]

        total_samples = len(rows)
        if total_samples == 0:
            return {
                "total_samples": 0,
                "window_size": window_size,
                "cold_start": True,
                "clean_success_count": 0,
                "repaired_success_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "reliability_rate": 1.0,
                "floor": floor,
                "floor_breached": False,
                "failed_calls": [],
                "recent_calls": []
            }

        clean_success = sum(1 for r in rows if r["validation_result"] == "valid" and r.get("repair_attempt", 0) == 0)
        repaired_success = sum(1 for r in rows if r["validation_result"] == "valid" and r.get("repair_attempt", 0) > 0)
        success_count = clean_success + repaired_success
        failed_calls = [r for r in rows if r["validation_result"] != "valid"]
        failure_count = len(failed_calls)
        reliability_rate = round(success_count / total_samples, 4)
        cold_start = total_samples < window_size
        floor_breached = (not cold_start) and (reliability_rate < floor)

        return {
            "total_samples": total_samples,
            "window_size": window_size,
            "cold_start": cold_start,
            "clean_success_count": clean_success,
            "repaired_success_count": repaired_success,
            "success_count": success_count,
            "failure_count": failure_count,
            "reliability_rate": reliability_rate,
            "floor": floor,
            "floor_breached": floor_breached,
            "failed_calls": failed_calls,
            "recent_calls": rows
        }

    def record_reliability_event(
        self,
        event_type: str,
        backend_from: str,
        backend_to: str,
        reliability_rate: float,
        window_size: int,
        failed_calls: list[dict[str, Any]],
        details: Optional[str] = None,
        timestamp: Optional[float] = None
    ) -> dict[str, Any]:
        """Record an alert or rollback event in the reliability audit history."""
        now = timestamp if timestamp is not None else time.time()
        failed_json = json.dumps(failed_calls)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reliability_events (
                    timestamp, event_type, backend_from, backend_to,
                    reliability_rate, window_size, failed_calls_count,
                    failed_calls_json, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now, event_type, backend_from, backend_to,
                reliability_rate, window_size, len(failed_calls),
                failed_json, details
            ))
            event_id = cursor.lastrowid
            conn.commit()
            return {
                "id": event_id,
                "timestamp": now,
                "event_type": event_type,
                "backend_from": backend_from,
                "backend_to": backend_to,
                "reliability_rate": reliability_rate,
                "window_size": window_size,
                "failed_calls_count": len(failed_calls),
                "failed_calls": failed_calls,
                "details": details
            }

    def get_reliability_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent reliability and rollback events."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM reliability_events
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            events = []
            for r in rows:
                ev = dict(r)
                if ev.get("failed_calls_json"):
                    try:
                        ev["failed_calls"] = json.loads(ev["failed_calls_json"])
                    except Exception:
                        ev["failed_calls"] = []
                events.append(ev)
            return events

