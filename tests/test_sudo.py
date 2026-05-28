import pytest

from agent.tools.os_tools import run_command
from agent.tools.sudo import (
    command_uses_sudo,
    format_sudo_required,
    is_sudo_required,
    parse_sudo_required,
    strip_sudo_prefix,
    wrap_with_sudo,
)


def test_command_uses_sudo() -> None:
    assert command_uses_sudo("sudo pacman -Syu")
    assert not command_uses_sudo("pacman -Q")


def test_sudo_marker_roundtrip() -> None:
    msg = format_sudo_required("sudo pacman -Syu")
    assert is_sudo_required(msg)
    assert parse_sudo_required(msg) == "sudo pacman -Syu"


def test_wrap_with_sudo() -> None:
    assert "sudo" in wrap_with_sudo("pacman -Q")


def test_strip_sudo_prefix() -> None:
    assert strip_sudo_prefix("sudo pacman -Syu") == "pacman -Syu"


@pytest.mark.asyncio
async def test_run_command_requests_sudo_password() -> None:
    out = await run_command(cmd="sudo echo test")
    assert is_sudo_required(out)
    assert parse_sudo_required(out) == "sudo echo test"
