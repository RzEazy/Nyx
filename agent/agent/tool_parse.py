import json
import re

FENCE_RE = re.compile(
    r"```(?:tool|json|javascript|js)?\s*\n?(.*?)\n?```",
    re.DOTALL | re.IGNORECASE,
)
TOOL_KEY_RE = re.compile(r'\{\s*"tool"\s*:', re.IGNORECASE)

_RESERVED_KEYS = frozenset({"tool", "args", "name", "function"})


def _coerce_tool_payload(data: object) -> dict | None:
    if not isinstance(data, dict) or "tool" not in data:
        return None
    name = str(data["tool"]).strip().replace("-", "_")
    args = data.get("args")
    if args is None:
        args = data.get("parameters") or data.get("arguments") or {}
    if not isinstance(args, dict):
        args = {}
    for key, value in data.items():
        if key in _RESERVED_KEYS:
            continue
        if key not in args:
            args[key] = value
    return {"tool": name, "args": args}


def _try_parse_json(raw: str) -> dict | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return _coerce_tool_payload(json.loads(raw))
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    if start >= 0:
        try:
            obj, _ = json.JSONDecoder().raw_decode(raw[start:])
            return _coerce_tool_payload(obj)
        except json.JSONDecodeError:
            return None
    return None


def parse_tool_call(text: str) -> dict | None:
    """Extract the first tool call from model output (tool/json fences or inline JSON)."""
    for match in FENCE_RE.finditer(text):
        payload = _try_parse_json(match.group(1))
        if payload:
            return payload

    for match in TOOL_KEY_RE.finditer(text):
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[match.start() :])
        except json.JSONDecodeError:
            continue
        payload = _coerce_tool_payload(obj)
        if payload:
            return payload

    return None


def looks_like_tool_attempt(text: str) -> bool:
    if '"tool"' in text or "'tool'" in text:
        return True
    return bool(FENCE_RE.search(text) and "tool" in text.lower())
