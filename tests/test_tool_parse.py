import json

from agent.agent.tool_parse import parse_tool_call


def test_parse_tool_fence() -> None:
    block = '```tool\n{"tool": "run_command", "args": {"cmd": "ls"}}\n```'
    assert parse_tool_call(block)["tool"] == "run_command"


def test_parse_json_fence() -> None:
    block = '```json\n{"tool": "run_command", "command": "echo hi"}\n```'
    data = parse_tool_call(block)
    assert data["tool"] == "run_command"
    assert data["args"]["command"] == "echo hi"


def test_parse_flat_args() -> None:
    text = '{"tool": "list_dir", "path": "/tmp"}'
    data = parse_tool_call(text)
    assert data["args"]["path"] == "/tmp"


def test_parse_inline_with_prose() -> None:
    text = (
        "I'll check that.\n```json\n"
        + json.dumps({"tool": "system_info", "args": {}})
        + "\n```"
    )
    assert parse_tool_call(text)["tool"] == "system_info"
