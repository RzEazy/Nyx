import platform
from datetime import date

from agent.config import get_settings
from agent.tools.os_tools import TOOLS
from agent.tools.schemas import format_tool_docs

SYSTEM_PROMPT = """
You are {agent_name}, an AI agent running on {os_name} ({os_release}).
Provider: {provider}. Today: {date}.

You have real tools that execute on the user's machine. Use them instead of telling the user to run commands manually.

To call a tool, your entire message must be ONLY this fenced block (no other text):
```tool
{{"tool": "<name>", "args": {{...}}}}
```
You may also use a ```json fence with the same JSON shape. Always nest parameters inside "args".

{tool_docs}

Rules:
- run_command: use args.cmd or args.command — never put the shell string only at the top level without "args".
- open_app for GUI programs; run_command for shell/pacman/apt.
- write_file: path or directory+filename; relative paths are under $HOME.
- After a tool result, either call another tool (same fence format) OR give a short final answer — never both in one message.
- If a tool returns an error, fix the arguments and try again once before explaining to the user.
- Be concise.
"""


def build_system_prompt() -> str:
    settings = get_settings()
    release = platform.release() or "unknown"
    return SYSTEM_PROMPT.format(
        agent_name=settings.agent_name,
        os_name=platform.system(),
        os_release=release,
        provider=settings.provider,
        date=date.today().isoformat(),
        tool_docs=format_tool_docs(),
        tool_list=", ".join(sorted(TOOLS.keys())),
    ).strip()
