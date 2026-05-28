import json

import pytest

from agent.agent.loop import AgentLoop
from agent.memory.db import MemoryDB
from agent.providers.base import ChatMessage, LLMProvider
from agent.tools.sudo import is_sudo_required


class MockProvider(LLMProvider):
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def chat(self, messages: list[ChatMessage], **kwargs) -> str:
        text = self._responses[self.calls]
        self.calls += 1
        return text

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] for _ in texts]


@pytest.mark.asyncio
async def test_loop_prompts_sudo_and_retries(tmp_path) -> None:
    tool_json = json.dumps(
        {"tool": "run_command", "args": {"cmd": "sudo echo sudo-ok"}}
    )
    memory = MemoryDB(db_path=str(tmp_path / "sudo.db"))
    passwords: list[str] = []

    async def provide_password(cmd: str) -> str:
        passwords.append(cmd)
        return "fake-password"

    loop = AgentLoop(
        provider=MockProvider(
            [f"```tool\n{tool_json}\n```", "Done running command."]
        ),
        memory=memory,
        session_id="sudo1",
        sudo_password_provider=provide_password,
    )
    result = await loop.run("run sudo echo")
    assert passwords == ["sudo echo sudo-ok"]
    tool_results = [e for e in loop.events if e.kind == "tool_result"]
    assert len(tool_results) >= 1
    assert not is_sudo_required(tool_results[-1].content)
    memory.close()
