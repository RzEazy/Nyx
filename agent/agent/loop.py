import inspect
import json
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from agent.agent.prompts import build_system_prompt
from agent.agent.tool_parse import looks_like_tool_attempt, parse_tool_call
from agent.config import get_settings
from agent.memory.db import MemoryDB
from agent.providers.base import ChatMessage, LLMProvider
from agent.tools.os_tools import TOOLS, normalize_tool_args
from agent.tools.sudo import is_sudo_required, parse_sudo_required

MAX_TOOL_ITERATIONS = 10

ChunkCallback = Callable[[str, bool], Awaitable[None]]
SudoPasswordProvider = Callable[[str], Awaitable[Optional[str]]]


@dataclass
class AgentEvent:
    kind: str  # "assistant" | "tool_call" | "tool_result" | "error"
    content: str
    tool_name: str | None = None


def _filter_kwargs(fn: callable, args: dict) -> dict:
    """Drop unknown keys unless the tool accepts **kwargs."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return args
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return args
    allowed = set(sig.parameters)
    return {k: v for k, v in args.items() if k in allowed}


@dataclass
class AgentLoop:
    provider: LLMProvider
    memory: MemoryDB
    session_id: str = "default"
    max_iterations: int = MAX_TOOL_ITERATIONS
    events: list[AgentEvent] = field(default_factory=list)
    sudo_password_provider: SudoPasswordProvider | None = None

    async def _execute_tool(self, name: str, args: dict) -> str:
        name = name.strip().replace("-", "_")
        fn = TOOLS.get(name)
        if fn is None:
            known = ", ".join(sorted(TOOLS.keys()))
            return f"Unknown tool: {name}. Available: {known}"
        if not isinstance(args, dict):
            args = {}
        args = normalize_tool_args(name, args)
        args = _filter_kwargs(fn, args)
        try:
            result = await fn(**args)
            if (
                name == "run_command"
                and is_sudo_required(result)
                and self.sudo_password_provider
            ):
                sudo_cmd = parse_sudo_required(result)
                if sudo_cmd:
                    password = await self.sudo_password_provider(sudo_cmd)
                    if password:
                        retry = dict(args)
                        retry["sudo_password"] = password
                        retry = normalize_tool_args(name, retry)
                        retry = _filter_kwargs(fn, retry)
                        result = await fn(**retry)
                    else:
                        result = "Sudo password not entered; command cancelled."
            return result
        except TypeError as e:
            return (
                f"Invalid arguments for {name}: {e}. "
                f"Received: {args}. Check tool docs in the system prompt."
            )
        except Exception as e:
            return f"Tool {name} failed: {e}"

    def _build_messages(self, user_input: str) -> list[ChatMessage]:
        settings = get_settings()
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=build_system_prompt()),
        ]
        summary = self.memory.get_latest_summary(self.session_id)
        if summary:
            messages.append(
                ChatMessage(
                    role="system",
                    content=f"Earlier conversation summary: {summary}",
                )
            )
        for m in self.memory.get_history(self.session_id, limit=settings.max_history):
            messages.append(m)
        messages.append(ChatMessage(role="user", content=user_input))
        return messages

    async def run(
        self,
        user_input: str,
        on_chunk: ChunkCallback | None = None,
    ) -> str:
        self.events = []
        settings = get_settings()
        messages = self._build_messages(user_input)
        self.memory.save_message(self.session_id, "user", user_input)

        final = ""
        parse_retries = 0
        for _iteration in range(self.max_iterations):
            response = await self.provider.chat(messages)
            self.memory.save_message(self.session_id, "assistant", response)
            self.events.append(AgentEvent(kind="assistant", content=response))

            tool_data = parse_tool_call(response)
            if not tool_data and looks_like_tool_attempt(response) and parse_retries < 2:
                parse_retries += 1
                messages.append(ChatMessage(role="assistant", content=response))
                messages.append(
                    ChatMessage(
                        role="user",
                        content=(
                            "Your tool JSON was not parsed. Reply with ONLY this block "
                            '(use ```tool fence, include "args"):\n'
                            '```tool\n{"tool": "run_command", "args": {"cmd": "..."}}\n```'
                        ),
                    )
                )
                continue

            if not tool_data:
                final = response
                if on_chunk:
                    await on_chunk(response, True)
                break

            parse_retries = 0
            name = str(tool_data.get("tool", ""))
            args = tool_data.get("args") or {}
            if not isinstance(args, dict):
                args = {}

            self.events.append(
                AgentEvent(
                    kind="tool_call",
                    content=json.dumps(tool_data),
                    tool_name=name,
                )
            )

            result = await self._execute_tool(name, args)
            self.events.append(
                AgentEvent(kind="tool_result", content=result, tool_name=name)
            )

            tool_msg = (
                f"Tool `{name}` returned:\n{result}\n\n"
                "Continue reasoning or give your final answer to the user."
            )
            messages.append(ChatMessage(role="assistant", content=response))
            messages.append(ChatMessage(role="user", content=tool_msg))
        else:
            final = "Max tool iterations reached."

        await self.memory.maybe_summarize(self.session_id, self.provider, settings)
        return final
