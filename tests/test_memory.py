from pathlib import Path

import pytest

from agent.memory.db import MemoryDB
from agent.providers.base import ChatMessage


@pytest.fixture
def memory_db(tmp_path: Path) -> MemoryDB:
    db = MemoryDB(db_path=str(tmp_path / "test.db"))
    yield db
    db.close()


def test_save_and_load_history(memory_db: MemoryDB) -> None:
    memory_db.save_message("s1", "user", "hello")
    memory_db.save_message("s1", "assistant", "hi there")
    history = memory_db.get_history("s1", limit=10)
    assert len(history) == 2
    assert history[0] == ChatMessage(role="user", content="hello")
    assert history[1] == ChatMessage(role="assistant", content="hi there")


@pytest.mark.asyncio
async def test_maybe_summarize(memory_db: MemoryDB) -> None:
    from agent.config import Settings

    class MockProvider:
        async def chat(self, messages, **kwargs) -> str:
            return "Summary of chat."

        async def embed(self, texts):
            return [[0.0] * 8 for _ in texts]

    settings = Settings(max_history=2)
    for i in range(3):
        memory_db.save_message("s2", "user", f"msg {i}")

    await memory_db.maybe_summarize("s2", MockProvider(), settings)
    assert memory_db.get_latest_summary("s2") == "Summary of chat."
