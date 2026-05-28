import pytest

from agent.tools import os_tools


@pytest.mark.asyncio
async def test_run_command() -> None:
    out = await os_tools.run_command("echo hello")
    assert "hello" in out


@pytest.mark.asyncio
async def test_run_command_command_alias() -> None:
    args = os_tools.normalize_tool_args(
        "run_command", {"command": "echo alias-ok"}
    )
    assert args["cmd"] == "echo alias-ok"
    out = await os_tools.run_command(**args)
    assert "alias-ok" in out


@pytest.mark.asyncio
async def test_run_command_missing() -> None:
    out = await os_tools.run_command()
    assert "missing" in out.lower()


@pytest.mark.asyncio
async def test_run_command_background() -> None:
    out = await os_tools.run_command("sleep 30", background=True)
    assert "background" in out.lower()


@pytest.mark.asyncio
async def test_list_dir(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("x")
    out = await os_tools.list_dir(str(tmp_path))
    assert "a.txt" in out


@pytest.mark.asyncio
async def test_read_write_file(tmp_path) -> None:
    path = tmp_path / "f.txt"
    w = await os_tools.write_file(path=str(path), content="content")
    assert "Wrote" in w
    r = await os_tools.read_file(path=str(path))
    assert r == "content"


@pytest.mark.asyncio
async def test_write_file_directory_and_filename(tmp_path) -> None:
    sub = tmp_path / "nested" / "dir"
    w = await os_tools.write_file(
        directory=str(sub),
        filename="out.txt",
        content="nested content",
    )
    assert "Wrote" in w
    assert (sub / "out.txt").read_text(encoding="utf-8") == "nested content"


@pytest.mark.asyncio
async def test_write_file_relative_to_home(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    w = await os_tools.write_file(path="Documents/notes.txt", content="note")
    assert "Wrote" in w
    assert (tmp_path / "Documents" / "notes.txt").read_text(encoding="utf-8") == "note"


@pytest.mark.asyncio
async def test_write_file_aliases() -> None:
    args = os_tools.normalize_tool_args(
        "write_file",
        {"dir": "/tmp", "file_name": "x.txt", "text": "hi"},
    )
    assert args["directory"] == "/tmp"
    assert args["filename"] == "x.txt"
    assert args["content"] == "hi"


@pytest.mark.asyncio
async def test_write_file_append(tmp_path) -> None:
    path = tmp_path / "a.log"
    await os_tools.write_file(path=str(path), content="line1\n")
    await os_tools.write_file(path=str(path), content="line2\n", append=True)
    assert path.read_text(encoding="utf-8") == "line1\nline2\n"


@pytest.mark.asyncio
async def test_open_app_missing() -> None:
    out = await os_tools.open_app(app="definitely-not-a-real-app-xyz-123")
    assert "Could not find" in out or "failed" in out.lower()


@pytest.mark.asyncio
async def test_open_app_path(tmp_path) -> None:
    f = tmp_path / "readme.txt"
    f.write_text("hello")
    out = await os_tools.open_app(path=str(f))
    assert "Launched" in out or "failed" not in out.lower()


@pytest.mark.asyncio
async def test_system_info() -> None:
    out = await os_tools.system_info()
    assert "CPU" in out


@pytest.mark.asyncio
async def test_find_files(tmp_path) -> None:
    (tmp_path / "match.py").write_text("")
    out = await os_tools.find_files("*.py", str(tmp_path))
    assert "match.py" in out
