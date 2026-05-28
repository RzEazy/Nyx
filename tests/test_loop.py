import json

import pytest

from agent.agent.loop import AgentLoop
from agent.memory.db import MemoryDB
from agent.providers.base import ChatMessage, LLMProvider


class MockProvider(LLMProvider):
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def chat(self, messages: list[ChatMessage], **kwargs) -> str:
        if self.calls >= len(self._responses):
            return "done"
        text = self._responses[self.calls]
        self.calls += 1
        return text

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


@pytest.mark.asyncio
async def test_loop_final_answer(tmp_path) -> None:
    memory = MemoryDB(db_path=str(tmp_path / "m.db"))
    loop = AgentLoop(
        provider=MockProvider(["Hello without tools."]),
        memory=memory,
        session_id="t1",
    )
    result = await loop.run("hi")
    assert result == "Hello without tools."
    memory.close()


@pytest.mark.asyncio
async def test_loop_tool_call(tmp_path) -> None:
    tool_json = json.dumps({"tool": "list_dir", "args": {"path": "."}})
    tool_response = f"```tool\n{tool_json}\n```"
    memory = MemoryDB(db_path=str(tmp_path / "m2.db"))
    loop = AgentLoop(
        provider=MockProvider([tool_response, "Listed files for you."]),
        memory=memory,
        session_id="t2",
    )
    result = await loop.run("list files")
    assert "Listed" in result
    assert any(e.kind == "tool_result" for e in loop.events)
    memory.close()


@pytest.mark.asyncio
async def test_loop_json_fence_flat_command(tmp_path) -> None:
    tool_response = '```json\n{"tool": "run_command", "command": "echo loop-ok"}\n```'
    memory = MemoryDB(db_path=str(tmp_path / "m3.db"))
    loop = AgentLoop(
        provider=MockProvider([tool_response, "Command succeeded."]),
        memory=memory,
        session_id="t3",
    )
    result = await loop.run("run echo")
    assert any(
        e.kind == "tool_result" and "loop-ok" in e.content for e in loop.events
    )
    assert "Command succeeded" in result
    memory.close()
