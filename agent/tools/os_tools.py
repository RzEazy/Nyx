import asyncio
import glob as glob_module
import shlex
import shutil
import sys
from pathlib import Path

import psutil
import pyautogui

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
    elif tool in ("mouse_click", "mouse_move"):
        if "coords" in out and "x" not in out:
            c = out.pop("coords")
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                out["x"], out["y"] = int(c[0]), int(c[1])
        if "position" in out and "x" not in out:
            c = out.pop("position")
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                out["x"], out["y"] = int(c[0]), int(c[1])
    elif tool == "type_text":
        for key in ("value", "content", "input"):
            if key in out and "text" not in out:
                out["text"] = out.pop(key)
    elif tool == "press_key":
        if "hotkey" in out and "key" not in out:
            out["key"] = out.pop("hotkey")
        for key in ("k", "button"):
            if key in out and "key" not in out:
                out["key"] = out.pop(key)
    elif tool == "hotkey":
        if "keys" in out and isinstance(out["keys"], str):
            out["keys"] = [k.strip() for k in out["keys"].split("+")]
        for key in ("combo", "combination", "shortcut"):
            if key in out and "keys" not in out:
                out["keys"] = out.pop(key)
    elif tool in ("click_text", "double_click_text", "right_click_text", "find_ui_element"):
        for key in ("label", "name", "query", "element"):
            if key in out and "text" not in out:
                out["text"] = out.pop(key)
        for key in ("btn", "button"):
            if key in out and "text" not in out:
                out["text"] = out.pop(key)
    elif tool == "navigate_to":
        for key in ("url", "link", "address"):
            if key in out and "url" not in out:
                out["url"] = out.pop(key)
    elif tool == "open_app_gui":
        for key in ("app", "name", "program", "application"):
            if key in out and "app" not in out:
                out["app"] = out.pop(key)
        if "app" in out and not out.get("app"):
            out["app"] = out.pop("app")
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


# ── Computer use tools (PyAutoGUI + vision) ─────────────────────────

import time as _time
import threading

_SNAP_CACHE = {"img": None, "elements": [], "time": 0, "lock": threading.Lock()}

_EASY_READER = None
try:
    import easyocr as _easy
    # Pre-init reader ONCE at module load so it's warm when tools are called
    _EASY_READER = _easy.Reader(["en"], gpu=False, verbose=False)
except Exception:
    _EASY_READER = None


def _downscale(image, max_dim: int = 1280):
    """Reduce image size for faster OCR. Returns (scaled_image, scale_x, scale_y)."""
    w, h = image.size
    if w <= max_dim and h <= max_dim:
        return image, 1.0, 1.0
    scale = max_dim / max(w, h)
    nw, nh = int(w * scale), int(h * scale)
    return image.resize((nw, nh), 1), scale, scale  # 1 = LANCZOS


def _fast_ocr(image) -> list[dict]:
    """OCR using EasyOCR singleton with image downscaling for speed."""
    if _EASY_READER is None:
        return []
    img, sx, sy = _downscale(image)
    import io, numpy as np
    arr = np.array(img)
    try:
        results = _EASY_READER.readtext(arr)
    except Exception:
        return []
    out = []
    for bbox, text, conf in results:
        if conf < 0.3:
            continue
        xs = [p[0] / sx for p in bbox]
        ys = [p[1] / sy for p in bbox]
        x_min, x_max = int(min(xs)), int(max(xs))
        y_min, y_max = int(min(ys)), int(max(ys))
        out.append({
            "text": text.strip(),
            "bbox": [x_min, y_min, x_max, y_max],
            "center": [(x_min + x_max) // 2, (y_min + y_max) // 2],
            "confidence": round(conf, 2),
        })
    return out


def _snapshot(force: bool = False) -> tuple:
    """Cached screenshot + OCR. Cache lasts 10s."""
    with _SNAP_CACHE["lock"]:
        now = _time.time()
        if not force and _SNAP_CACHE["img"] is not None and now - _SNAP_CACHE["time"] < 10.0:
            return _SNAP_CACHE["img"], _SNAP_CACHE["elements"]
    from agent.desktop.config import DesktopConfig
    from agent.desktop.vision import ScreenCapture
    cap = ScreenCapture(DesktopConfig())
    img = cap.capture()
    elements = _fast_ocr(img)
    with _SNAP_CACHE["lock"]:
        _SNAP_CACHE["img"] = img
        _SNAP_CACHE["elements"] = elements
        _SNAP_CACHE["time"] = _time.time()
    return img, elements


def _find(elements: list[dict], query: str) -> dict | None:
    """Search OCR results for text containing query (case-insensitive)."""
    q = query.lower().strip()
    for el in elements:
        if q in el["text"].lower():
            return el
    for el in elements:
        if any(q == w for w in el["text"].lower().split()):
            return el
    return None


def _ensure_not_corner():
    """Nudge mouse away from (0,0) if there."""
    try:
        x, y = pyautogui.position()
        if x < 5 and y < 5:
            pyautogui.moveTo(200, 200, duration=0.1)
            _time.sleep(0.1)
    except Exception:
        pass


async def screenshot() -> str:
    """Capture screen + OCR. Returns all visible UI elements with positions."""
    from agent.desktop.app_control.windows import WindowManager
    from agent.desktop.config import DesktopConfig
    from agent.desktop.vision import ScreenCapture
    img, elements = _snapshot(force=True)
    cap = ScreenCapture(DesktopConfig())
    path = cap.save()
    active = WindowManager.active()
    lines = [f"Screen: {active}", f"Image: {path}"]
    if elements:
        for el in elements[:35]:
            lines.append(f"  '{el['text']}' at ({el['center'][0]},{el['center'][1]})")
    else:
        lines.append("  (no text detected)")
    return "\n".join(lines)


async def find_ui_element(text: str = "") -> str:
    """Find a UI element by its text label. Returns coordinates."""
    if not text:
        return "find_ui_element: provide text"
    _, elements = _snapshot()
    el = _find(elements, text)
    if el:
        return f"Found '{text}' at ({el['center'][0]},{el['center'][1]})"
    return f"'{text}' not visible. Try screenshot() first."


async def click_text(text: str = "", button: str = "left") -> str:
    """Find text on screen via OCR, move mouse, and click."""
    if not text:
        return "click_text: provide text to click"
    _, elements = _snapshot()
    el = _find(elements, text)
    if not el:
        return f"'{text}' not visible. Use screenshot() to see available elements."
    cx, cy = el["center"]
    _ensure_not_corner()
    try:
        pyautogui.moveTo(cx, cy, duration=0.25)
        pyautogui.click(button=button)
        return f"Clicked '{text}' at ({cx},{cy})"
    except pyautogui.FailSafeException:
        return "Fail-safe: mouse was at corner, retry after moving it."
    except Exception as e:
        return f"click_text error: {e}"


async def double_click_text(text: str = "") -> str:
    """Find text on screen via OCR and double-click."""
    if not text:
        return "double_click_text: provide text"
    _, elements = _snapshot()
    el = _find(elements, text)
    if not el:
        return f"'{text}' not visible."
    cx, cy = el["center"]
    _ensure_not_corner()
    try:
        pyautogui.moveTo(cx, cy, duration=0.25)
        pyautogui.doubleClick()
        return f"Double-clicked '{text}' at ({cx},{cy})"
    except pyautogui.FailSafeException:
        return "Fail-safe triggered."
    except Exception as e:
        return f"double_click_text error: {e}"


async def right_click_text(text: str = "") -> str:
    """Find text on screen via OCR and right-click."""
    if not text:
        return "right_click_text: provide text"
    _, elements = _snapshot()
    el = _find(elements, text)
    if not el:
        return f"'{text}' not visible."
    cx, cy = el["center"]
    _ensure_not_corner()
    try:
        pyautogui.moveTo(cx, cy, duration=0.25)
        pyautogui.rightClick()
        return f"Right-clicked '{text}' at ({cx},{cy})"
    except pyautogui.FailSafeException:
        return "Fail-safe triggered."
    except Exception as e:
        return f"right_click_text error: {e}"


async def mouse_click(x: int = 0, y: int = 0, button: str = "left") -> str:
    """Click at coordinates. Use click_text() instead if you have a text label."""
    _ensure_not_corner()
    try:
        pyautogui.click(int(x), int(y), button=button)
        return f"Clicked {button} at ({x},{y})"
    except pyautogui.FailSafeException:
        return "Fail-safe triggered."


async def mouse_move(x: int, y: int) -> str:
    """Move mouse to (x,y)."""
    _ensure_not_corner()
    try:
        pyautogui.moveTo(int(x), int(y), duration=0.25)
        return f"Moved mouse to ({x},{y})"
    except pyautogui.FailSafeException:
        return "Fail-safe triggered."


async def type_text(text: str = "") -> str:
    """Type text at current cursor position."""
    _ensure_not_corner()
    if not text:
        return "type_text: no text provided"
    try:
        pyautogui.typewrite(text, interval=0.015)
        return "Typed: " + text[:80]
    except pyautogui.FailSafeException:
        return "Fail-safe triggered."


async def press_key(key: str = "") -> str:
    """Press a single key: enter, tab, win, escape, f6, ctrl, etc."""
    if not key:
        return "press_key: provide a key"
    try:
        pyautogui.press(key.lower())
        return "Pressed key: " + key
    except pyautogui.FailSafeException:
        return "Fail-safe triggered."


async def hotkey(keys: str | list[str] = "") -> str:
    """Press a key combination. Pass as list: ['ctrl','l'] or string: 'ctrl+l'."""
    if isinstance(keys, str):
        keys = [k.strip() for k in keys.split("+")]
    try:
        pyautogui.hotkey(*keys)
        return "Hotkey: " + "+".join(keys)
    except pyautogui.FailSafeException:
        return "Fail-safe triggered."


async def scroll(amount: int = -3) -> str:
    """Scroll. Positive = up, negative = down."""
    try:
        pyautogui.scroll(amount)
        direction = "up" if amount > 0 else "down"
        return f"Scrolled {direction} by {abs(amount)}"
    except pyautogui.FailSafeException:
        return _FAILSAFE_HELP


async def get_mouse_position() -> str:
    """Return current mouse cursor coordinates."""
    try:
        pos = pyautogui.position()
        return f"Mouse position: ({pos.x}, {pos.y})"
    except pyautogui.FailSafeException:
        return _FAILSAFE_HELP


async def navigate_to(url: str = "") -> str:
    """Focus URL bar (Ctrl+L) and type a URL, then Enter."""
    if not url:
        return "navigate_to: provide a url"
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        pyautogui.hotkey("ctrl", "l")
        await asyncio.sleep(0.3)
        pyautogui.typewrite(url, interval=0.03)
        await asyncio.sleep(0.2)
        pyautogui.press("enter")
        return f"Navigated to {url}"
    except pyautogui.FailSafeException:
        return _FAILSAFE_HELP


async def open_app_gui(app: str = "") -> str:
    """Open a GUI app using Win key search. e.g. 'chrome', 'notepad', 'calculator'."""
    if not app:
        return "open_app_gui: provide an app name"
    try:
        pyautogui.hotkey("win")
        await asyncio.sleep(0.4)
        pyautogui.typewrite(app, interval=0.04)
        await asyncio.sleep(1.0)
        pyautogui.press("enter")
        return f"Opened '{app}' via Win key search"
    except pyautogui.FailSafeException:
        return _FAILSAFE_HELP


TOOLS: dict[str, callable] = {
    "run_command": run_command,
    "open_app": open_app,
    "list_dir": list_dir,
    "read_file": read_file,
    "write_file": write_file,
    "system_info": system_info,
    "find_files": find_files,
    "screenshot": screenshot,
    "find_ui_element": find_ui_element,
    "click_text": click_text,
    "double_click_text": double_click_text,
    "right_click_text": right_click_text,
    "mouse_click": mouse_click,
    "mouse_move": mouse_move,
    "type_text": type_text,
    "press_key": press_key,
    "hotkey": hotkey,
    "scroll": scroll,
    "get_mouse_position": get_mouse_position,
    "navigate_to": navigate_to,
    "open_app_gui": open_app_gui,
}
