"""Sudo password flow — marker protocol between run_command and the TUI."""

import json
import re
import shlex

SUDO_MARKER = "__NYX_SUDO_REQUIRED__"

_SUDO_IN_CMD = re.compile(r"\bsudo\b")
_PASSWORD_HINTS = (
    "a password is required",
    "sudo: a terminal is required to read the password",
    "sudo: no password was provided",
    "sudo: 1 incorrect password attempt",
    "[sudo] password for",
)


def command_uses_sudo(cmd: str) -> bool:
    return bool(_SUDO_IN_CMD.search(cmd))


def output_needs_sudo_password(stderr: str, stdout: str = "") -> bool:
    combined = f"{stderr}\n{stdout}".lower()
    return any(h in combined for h in _PASSWORD_HINTS)


def wrap_with_sudo(cmd: str) -> str:
    if command_uses_sudo(cmd):
        return cmd.strip()
    return f"sudo sh -c {shlex.quote(cmd.strip())}"


def strip_sudo_prefix(cmd: str) -> str:
    return re.sub(r"^\s*sudo\s+", "", cmd.strip(), count=1)


def format_sudo_required(cmd: str) -> str:
    return f"{SUDO_MARKER}\n{json.dumps({'cmd': cmd})}"


def parse_sudo_required(text: str) -> str | None:
    if not text.startswith(SUDO_MARKER):
        return None
    payload = text[len(SUDO_MARKER) :].strip()
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    cmd = data.get("cmd")
    return str(cmd) if cmd else None


def is_sudo_required(text: str) -> bool:
    return text.startswith(SUDO_MARKER)
