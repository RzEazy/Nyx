import sqlite3
from pathlib import Path

from agent.config import Settings, get_settings
from agent.providers.base import ChatMessage, LLMProvider

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    role TEXT,
    content TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    summary TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


class MemoryDB:
    def __init__(self, db_path: str | None = None) -> None:
        settings = get_settings()
        self._path = Path(db_path or settings.db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def save_message(self, session_id: str, role: str, content: str) -> None:
        self._conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        self._conn.commit()

    def get_history(self, session_id: str, limit: int = 20) -> list[ChatMessage]:
        rows = self._conn.execute(
            """
            SELECT role, content FROM messages
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        rows = list(reversed(rows))
        return [ChatMessage(role=r["role"], content=r["content"]) for r in rows]

    def get_latest_summary(self, session_id: str) -> str | None:
        row = self._conn.execute(
            """
            SELECT summary FROM summaries
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
        return row["summary"] if row else None

    def save_summary(self, session_id: str, summary: str) -> None:
        self._conn.execute(
            "INSERT INTO summaries (session_id, summary) VALUES (?, ?)",
            (session_id, summary),
        )
        self._conn.commit()

    def message_count(self, session_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return int(row["c"])

    async def maybe_summarize(
        self,
        session_id: str,
        provider: LLMProvider,
        settings: Settings | None = None,
    ) -> None:
        settings = settings or get_settings()
        if self.message_count(session_id) <= settings.max_history:
            return
        history = self.get_history(session_id, limit=settings.max_history)
        transcript = "\n".join(f"{m.role}: {m.content}" for m in history)
        prompt = [
            ChatMessage(
                role="user",
                content=f"Summarize this conversation in 3 sentences:\n\n{transcript}",
            )
        ]
        summary = await provider.chat(prompt)
        self.save_summary(session_id, summary.strip())
