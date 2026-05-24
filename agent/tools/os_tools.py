import asyncio
import glob as glob_module
import shlex
import shutil
import sys
from pathlib import Path

import psutil

from agent.tools.sudo import (
    command_uses_sudo,
    format_sudo_required,
    output_needs_sudo_password,
    strip_sudo_prefix,
    wrap_with_sudo,
)

COMMAND_TIMEOUT = 10
SUDO_COMMAND_TIMEOUT = 120
LAUNCH_TIMEOUT = 5


async def _communicate_with_timeout(
    proc: asyncio.subprocess.Process,
    timeout: float,
    input_data: bytes | None = None,
) -> tuple[bytes, bytes]:
    try:
        return await asyncio.wait_for(proc.communicate(input=input_data), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await asyncio.wait_for(proc.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass
        raise

# Normalized app name -> executables tried in order (Linux/desktop)
APP_COMMANDS: dict[str, list[str]] = {
    "firefox": ["firefox"],
    "chrome": ["google-chrome-stable", "google-chrome", "chromium", "chromium-browser"],
    "chromium": ["chromium", "chromium-browser", "google-chrome"],
    "code": ["code", "codium", "code-oss"],
    "vscode": ["code", "codium"],
    "vs code": ["code", "codium"],
    "visual studio code": ["code", "codium"],
    "spotify": ["spotify"],
    "discord": ["discord", "discord-canary"],
    "telegram": ["telegram-desktop"],
    "steam": ["steam"],
    "terminal": ["kitty", "alacritty", "konsole", "gnome-terminal", "xterm"],
    "kitty": ["kitty"],
    "alacritty": ["alacritty"],
    "files": ["nautilus", "dolphin", "thunar", "pcmanfm", "nemo"],
    "file manager": ["nautilus", "dolphin", "thunar", "pcmanfm"],
    "nautilus": ["nautilus"],
    "calculator": ["gnome-calculator", "kcalc", "galculator"],
    "gedit": ["gedit", "mousepad", "pluma"],
    "text editor": ["gedit", "mousepad", "pluma", "kate"],
    "gimp": ["gimp"],
    "vlc": ["vlc"],
    "obs": ["obs"],
    "libreoffice": ["libreoffice"],
}


def _normalize_app_key(name: str) -> str:
    return name.strip().lower().replace("_", "-").replace("  ", " ")


def _find_executable(candidates: list[str]) -> str | None:
    for name in candidates:
        found = shutil.which(name)
        if found:
            return found
    return None


def resolve_user_path(
    path: str | None = None,
    *,
    directory: str | None = None,
    filename: str | None = None,
    file_path: str | None = None,
    must_exist: bool = False,
) -> Path:
    """Resolve a user path: ~ expansion, optional directory+filename, relative → $HOME."""
    raw = (path or file_path or "").strip()
    dir_part = (directory or "").strip()
    name_part = (filename or "").strip()

    if dir_part and name_part:
        raw = str(Path(dir_part) / name_part)
    elif dir_part and raw:
        dir_path = Path(dir_part).expanduser()
        if dir_path.is_dir() or not raw:
            raw = str(dir_path / raw)
        else:
            raw = str(Path(dir_part) / raw) if not Path(raw).name == raw else raw
    elif dir_part and not raw:
        raise ValueError("directory given without filename or path")

    if not raw:
        raise ValueError("no path provided (use path, file_path, or directory+filename)")

    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = Path.home() / p
    p = p.resolve()

    if must_exist and not p.exists():
        raise FileNotFoundError(f"Path does not exist: {p}")
    return p


def normalize_tool_args(tool: str, args: dict) -> dict:
    """Map common LLM argument aliases to what our tools expect."""
    out = dict(args)
    if tool == "write_file":
        for key in ("file", "filepath", "file_name", "name"):
            if key in out and "path" not in out and "file_path" not in out:
                out["filename"] = out.pop(key)
        if "dir" in out and "directory" not in out:
            out["directory"] = out.pop("dir")
        if "text" in out and "content" not in out:
            out["content"] = out.pop("text")
        if "data" in out and "content" not in out:
            out["content"] = out.pop("data")
    elif tool == "open_app":
        for key in ("application", "program", "app_name"):
            if key in out and "app" not in out and "name" not in out:
                out["app"] = out.pop(key)
        if "file" in out and "path" not in out and "target" not in out:
            out["path"] = out.pop("file")
        if "folder" in out and "path" not in out:
            out["path"] = out.pop("folder")
        if "command" in out and "app" not in out:
            out["app"] = out.pop("command")
    elif tool == "run_command":
        for key in ("command", "shell", "script", "exec", "input"):
            if key in out and "cmd" not in out:
                out["cmd"] = out.pop(key)
    elif tool == "read_file":
        for key in ("file", "filepath", "file_path"):
            if key in out and "path" not in out:
                out["path"] = out.pop(key)
    elif tool == "list_dir":
        for key in ("dir", "directory", "folder"):
            if key in out and "path" not in out:
                out["path"] = out.pop(key)
    elif tool == "find_files":
        if "glob" in out and "pattern" not in out:
            out["pattern"] = out.pop("glob")
        if "dir" in out and "root" not in out:
            out["root"] = out.pop("dir")
    return out


async def _launch_detached(argv: list[str]) -> str:
    """Start a process detached; suitable for GUI apps."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
    except FileNotFoundError:
        return f"Executable not found: {argv[0]}"
    except Exception as e:
        return f"Launch failed: {e}"

    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=LAUNCH_TIMEOUT)
    except asyncio.TimeoutError:
        return f"Launched (background): {' '.join(shlex.quote(a) for a in argv)}"

    err = (stderr or b"").decode(errors="replace").strip()
    if proc.returncode == 0:
        return f"Launched: {' '.join(shlex.quote(a) for a in argv)}"
    if proc.returncode is None:
        return f"Launched: {' '.join(shlex.quote(a) for a in argv)}"
    detail = f"\nstderr: {err}" if err else ""
    return f"Launch failed (exit {proc.returncode}){detail}"


def _open_target_command(target: str) -> list[str]:
    p = Path(target).expanduser().resolve()
    if sys.platform == "darwin":
        return ["open", str(p)]
    if sys.platform == "win32":
        return ["cmd", "/c", "start", "", str(p)]
    return ["xdg-open", str(p)]


def _format_result(code: int | None, out: str, err: str) -> str:
    parts = [f"exit code: {code}"]
    if out:
        parts.append(f"stdout:\n{out}")
    if err:
        parts.append(f"stderr:\n{err}")
    return "\n".join(parts)


async def _run_with_sudo(inner: str, password: str) -> tuple[int | None, str, str]:
    """Run command under sudo -S (password via stdin, not echoed)."""
    proc = await asyncio.create_subprocess_exec(
        "sudo",
        "-S",
        "-p",
        "",
        "sh",
        "-c",
        inner,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await _communicate_with_timeout(
        proc,
        SUDO_COMMAND_TIMEOUT,
        input_data=(password + "\n").encode(),
    )
    return (
        proc.returncode,
        stdout.decode(errors="replace"),
        stderr.decode(errors="replace"),
    )


async def run_command(cmd: str = "", background: bool = False, **kwargs) -> str:
    """Run a shell command. Pass the shell string as `cmd` (aliases: command, shell)."""
    shell = (cmd or kwargs.get("command") or kwargs.get("shell") or "").strip()
    sudo_password = (kwargs.get("sudo_password") or "").strip()
    if not shell:
        return (
            "run_command failed: missing command string. "
            'Use args: {"cmd": "your command here"} or {"command": "..."}'
        )
    try:
        if background:
            if command_uses_sudo(shell) and not sudo_password:
                return format_sudo_required(shell)
            proc = await asyncio.create_subprocess_shell(
                shell,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            try:
                _, stderr = await asyncio.wait_for(proc.communicate(), timeout=3)
            except asyncio.TimeoutError:
                return f"Started in background: {shell}"
            err = (stderr or b"").decode(errors="replace").strip()
            if proc.returncode == 0:
                return f"Started in background: {shell}"
            return f"Background command failed (exit {proc.returncode})\n{err}"

        if command_uses_sudo(shell) and not sudo_password:
            return format_sudo_required(shell)

        if sudo_password:
            inner = strip_sudo_prefix(shell) if command_uses_sudo(shell) else shell
            code, out, err = await _run_with_sudo(inner, sudo_password)
            if code != 0 and output_needs_sudo_password(err, out):
                return "sudo failed: incorrect password or insufficient privileges."
            return _format_result(code, out, err)

        proc = await asyncio.create_subprocess_shell(
            shell,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await _communicate_with_timeout(proc, COMMAND_TIMEOUT)
        out = stdout.decode(errors="replace")
        err = stderr.decode(errors="replace")
        code = proc.returncode

        if code != 0 and (
            output_needs_sudo_password(err, out)
            or "permission denied" in err.lower()
        ):
            return format_sudo_required(wrap_with_sudo(shell))

        return _format_result(code, out, err)
    except asyncio.TimeoutError:
        limit = SUDO_COMMAND_TIMEOUT if sudo_password else COMMAND_TIMEOUT
        return f"Command timed out after {limit}s"
    except FileNotFoundError:
        return "run_command failed: sudo not found on this system"
    except Exception as e:
        return f"Command failed: {e}"


async def open_app(
    app: str = "",
    name: str = "",
    target: str = "",
    path: str = "",
    url: str = "",
    args: str | list[str] | None = None,
) -> str:
    """
    Open a GUI application or open a file/URL with the system handler.
    Prefer this over run_command for launching apps (run_command times out on GUI).
    """
    app_name = (app or name).strip()
    open_target = (target or path or url).strip()

    extra: list[str] = []
    if args:
        if isinstance(args, str):
            extra = shlex.split(args)
        else:
            extra = [str(a) for a in args]

    if open_target:
        try:
            resolved = resolve_user_path(open_target)
            return await _launch_detached(_open_target_command(str(resolved)))
        except Exception as e:
            if open_target.startswith(("http://", "https://", "mailto:")):
                return await _launch_detached(_open_target_command(open_target))
            return f"open_app failed: {e}"

    if not app_name:
        return (
            "open_app needs app (e.g. firefox, code) or path/url/target "
            "(file, folder, or https://...)"
        )

    key = _normalize_app_key(app_name)
    candidates = APP_COMMANDS.get(key)
    if not candidates:
        candidates = [app_name, key.replace(" ", "-"), key.replace(" ", "")]

    executable = _find_executable(candidates)
    if not executable:
        if shutil.which("gtk-launch"):
            desktop_id = key.replace(" ", "-")
            return await _launch_detached(["gtk-launch", desktop_id, *extra])
        return (
            f"Could not find application '{app_name}'. "
            f"Tried: {', '.join(candidates)}. "
            "Install it or use open_app with path= to open a file via xdg-open."
        )

    argv = [executable, *extra]
    return await _launch_detached(argv)


async def list_dir(path: str) -> str:
    try:
        p = resolve_user_path(path, must_exist=True)
        if not p.is_dir():
            return f"Not a directory: {p}"
        entries = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        lines = []
        for e in entries:
            tag = "dir" if e.is_dir() else "file"
            lines.append(f"[{tag}] {e.name}")
        return "\n".join(lines) if lines else "(empty directory)"
    except Exception as e:
        return f"list_dir failed: {e}"


async def read_file(
    path: str = "",
    file_path: str = "",
    max_bytes: int = 8192,
    **kwargs,
) -> str:
    try:
        p = resolve_user_path(path=path or file_path or kwargs.get("file"))
        if not p.is_file():
            return f"Not a file: {p}"
        data = p.read_bytes()[:max_bytes]
        text = data.decode(errors="replace")
        if p.stat().st_size > max_bytes:
            text += f"\n... (truncated at {max_bytes} bytes)"
        return text
    except Exception as e:
        return f"read_file failed: {e}"


async def write_file(
    path: str = "",
    content: str = "",
    directory: str = "",
    filename: str = "",
    file_path: str = "",
    append: bool = False,
    **kwargs,
) -> str:
    """Write text using path/file_path or directory+filename; relative paths use $HOME."""
    try:
        text = content if content != "" else kwargs.get("text", kwargs.get("data", ""))
        if text is None:
            text = ""
        if not isinstance(text, str):
            text = str(text)

        p = resolve_user_path(
            path=path or file_path or kwargs.get("file"),
            directory=directory or kwargs.get("dir"),
            filename=filename or kwargs.get("file_name") or kwargs.get("name"),
        )

        if p.exists() and p.is_dir():
            return f"write_file failed: {p} is a directory; provide a file path or filename"

        p.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with p.open(mode, encoding="utf-8") as f:
            f.write(text)

        action = "Appended" if append else "Wrote"
        return f"{action} {len(text)} bytes to {p}"
    except PermissionError:
        return f"write_file failed: permission denied for {path or directory or file_path}"
    except Exception as e:
        return f"write_file failed: {e}"


async def system_info() -> str:
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = shutil.disk_usage("/")
        return (
            f"CPU usage: {cpu}%\n"
            f"RAM: {mem.percent}% used ({mem.used // (1024**2)} MB / "
            f"{mem.total // (1024**2)} MB)\n"
            f"Disk (/): {disk.used // (1024**3)} GB / {disk.total // (1024**3)} GB used"
        )
    except Exception as e:
        return f"system_info failed: {e}"


async def find_files(pattern: str, root: str = ".") -> str:
    try:
        base = resolve_user_path(root)
        matches = sorted(glob_module.glob(str(base / pattern), recursive=True))[:50]
        if not matches:
            return f"No matches for pattern '{pattern}' under {base}"
        extra = ""
        full = list(glob_module.glob(str(base / pattern), recursive=True))
        if len(full) > 50:
            extra = f"\n... and {len(full) - 50} more"
        return "\n".join(matches) + extra
    except Exception as e:
        return f"find_files failed: {e}"


TOOLS: dict[str, callable] = {
    "run_command": run_command,
    "open_app": open_app,
    "list_dir": list_dir,
    "read_file": read_file,
    "write_file": write_file,
    "system_info": system_info,
    "find_files": find_files,
}
