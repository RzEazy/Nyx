import asyncio
import glob as glob_module
import os
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
    elif tool == "write_code":
        for key in ("content", "text", "source"):
            if key in out and "code" not in out:
                out["code"] = out.pop(key)
    elif tool == "edit_file":
        for key in ("path", "file", "file_path", "name", "save_as", "output"):
            if key in out and "filepath" not in out:
                out["filepath"] = out.pop(key)
        for key in ("old_string", "old_text", "find", "search"):
            if key in out and "old" not in out:
                out["old"] = out.pop(key)
        for key in ("new_string", "new_text", "replace", "replacement"):
            if key in out and "new" not in out:
                out["new"] = out.pop(key)
        for key in ("editor", "program", "application"):
            if key in out and "app" not in out:
                out["app"] = out.pop(key)
    elif tool == "search_on_page":
        for key in ("q", "search", "text"):
            if key in out and "query" not in out:
                out["query"] = out.pop(key)
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


async def edit_file(filepath: str = "", old: str = "", new: str = "") -> str:
    """Find and replace text in a file. Perfect for fixing bugs without rewriting the whole file.

    Args:
        filepath: path to the file to edit
        old: the exact text to find (must match exactly)
        new: the replacement text
    """
    if not filepath or not old:
        return "edit_file: provide filepath and old text to find"
    try:
        p = Path(filepath).resolve()
        if not p.exists():
            return f"edit_file: {filepath} not found"
        text = p.read_text(encoding="utf-8")
        if old not in text:
            return f"edit_file: could not find:\n---\n{old}\n---\nin {filepath}"
        count = text.count(old)
        text = text.replace(old, new, 1)
        p.write_text(text, encoding="utf-8")
        return f"Replaced 1 occurrence in {filepath}"
    except Exception as e:
        return f"edit_file error: {e}"


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

# ── Tesseract (fast, ~200ms) ──────────────────────────────────────
_HAS_TESSERACT = False
try:
    import pytesseract as _pyt
    # 1. Check TESSERACT_PATH env var
    _tess_env = os.environ.get("TESSERACT_PATH", "")
    if _tess_env:
        _p = Path(_tess_env)
        if _p.exists():
            _pyt.pytesseract.tesseract_cmd = str(_p)
            _HAS_TESSERACT = True
    # 2. Check common install locations
    if not _HAS_TESSERACT:
        for _p in [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
            Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Tesseract-OCR" / "tesseract.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "Tesseract-OCR" / "tesseract.exe",
        ]:
            if _p.exists():
                _pyt.pytesseract.tesseract_cmd = str(_p)
                _HAS_TESSERACT = True
                break
    # 3. Fallback: check if pytesseract can find it in PATH
    if not _HAS_TESSERACT:
        import subprocess
        try:
            subprocess.run([_pyt.pytesseract.tesseract_cmd, "--version"],
                           capture_output=True, timeout=5)
            _HAS_TESSERACT = True
        except Exception:
            pass
except Exception:
    pass

# ── EasyOCR fallback (lazy init, ~5-8s first use) ───────────────
_EASY_READER = None
_EASY_AVAILABLE = False
try:
    import easyocr as _easy
    _EASY_AVAILABLE = True
    _easy_imported = _easy  # keep reference for lazy init
except Exception:
    pass


def _downscale(image, max_dim: int = 1280):
    """Reduce image size for faster OCR. Returns (scaled_image, scale_x, scale_y)."""
    w, h = image.size
    if w <= max_dim and h <= max_dim:
        return image, 1.0, 1.0
    scale = max_dim / max(w, h)
    nw, nh = int(w * scale), int(h * scale)
    return image.resize((nw, nh), 1), scale, scale  # 1 = LANCZOS


def _tesseract_ocr(image) -> list[dict]:
    """OCR using Tesseract. Fast (~200-500ms) vs EasyOCR (~5-8s)."""
    if not _HAS_TESSERACT:
        return []
    import numpy as np
    arr = np.array(image.convert("L"))  # grayscale for speed
    try:
        data = _pyt.image_to_data(arr, output_type=_pyt.Output.DICT)
    except Exception:
        return []
    out = []
    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        conf = int(data["conf"][i]) / 100.0
        if not text or conf < 0.3:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        if w < 2 or h < 2:
            continue
        out.append({
            "text": text,
            "bbox": [x, y, x + w, y + h],
            "center": [x + w // 2, y + h // 2],
            "confidence": round(conf, 2),
        })
    return out


def _fast_ocr(image) -> list[dict]:
    """OCR: Tesseract primary (~200ms), EasyOCR fallback (~5-8s)."""
    if _HAS_TESSERACT:
        result = _tesseract_ocr(image)
        if result:
            return result
    global _EASY_READER
    if _EASY_READER is None and _EASY_AVAILABLE:
        # Lazy init — only pay the 5-8s cost if Tesseract actually fails
        try:
            _EASY_READER = _easy.Reader(["en"], gpu=False, verbose=False)
        except Exception:
            pass
    if _EASY_READER is None:
        return []
    img, sx, sy = _downscale(image)
    import numpy as np
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


# ── Region helpers ────────────────────────────────────────────────────

_CHROME_REGION = "8,0,100,100"  # skip top 8% (browser chrome)


def _parse_region(region_str: str, img_size: tuple) -> tuple:
    """Parse region string into pixel bounds.
    Format: 'top%,left%,bottom%,right%' e.g. '8,0,100,100'
    Returns (x1, y1, x2, y2) in pixels.
    """
    if not region_str:
        return (0, 0, img_size[0], img_size[1])
    parts = region_str.replace(",", " ").split()
    if len(parts) != 4:
        return (0, 0, img_size[0], img_size[1])
    w, h = img_size
    t, l, b, r = (float(p) / 100 for p in parts)
    return (int(w * l), int(h * t), int(w * r), int(h * b))


def _filter_by_region(elements: list[dict], x1: int, y1: int, x2: int, y2: int) -> list[dict]:
    """Filter elements to those whose center falls within the region."""
    return [el for el in elements
            if x1 <= el["center"][0] <= x2 and y1 <= el["center"][1] <= y2]


# ── Snapshot with region support ──────────────────────────────────────


def _snapshot(force: bool = False, region: str = "") -> tuple:
    """Cached screenshot + OCR. Cache lasts 10s.
    region: 'top%,left%,bottom%,right%' e.g. '8,0,100,100' skips top 8%.
    """
    with _SNAP_CACHE["lock"]:
        now = _time.time()
        if not force and _SNAP_CACHE["img"] is not None and now - _SNAP_CACHE["time"] < 10.0:
            img = _SNAP_CACHE["img"]
            elements = _SNAP_CACHE["elements"]
        else:
            from agent.desktop.config import DesktopConfig
            from agent.desktop.vision import ScreenCapture
            cap = ScreenCapture(DesktopConfig())
            img = cap.capture()
            elements = _fast_ocr(img)
            _SNAP_CACHE["img"] = img
            _SNAP_CACHE["elements"] = elements
            _SNAP_CACHE["time"] = _time.time()

    if region:
        x1, y1, x2, y2 = _parse_region(region, img.size)
        elements = _filter_by_region(elements, x1, y1, x2, y2)

    return img, elements


# ── Group text into content items ──────────────────────────────────────


def _group_by_proximity(elements: list[dict], max_gap: int = 45) -> list[list[dict]]:
    """Group OCR elements by vertical proximity. Each group is a content item."""
    sorted_el = sorted(elements, key=lambda x: (x["center"][1], x["center"][0]))
    groups = []
    cur = []
    last_y = -100
    for el in sorted_el:
        cy = el["center"][1]
        if cur and cy - last_y > max_gap:
            groups.append(cur)
            cur = []
        cur.append(el)
        last_y = cy
    if cur:
        groups.append(cur)
    return groups


# ── Tools ──────────────────────────────────────────────────────────────


async def screenshot(region: str = "") -> str:
    """Capture screen + OCR. Returns all visible UI elements with positions.
    region: optional 'top%,left%,bottom%,right%' to filter (e.g. '8,0,100,100' skips browser chrome).
    """
    from agent.desktop.app_control.windows import WindowManager
    from agent.desktop.config import DesktopConfig
    from agent.desktop.vision import ScreenCapture
    img, elements = _snapshot(force=True, region=region)
    cap = ScreenCapture(DesktopConfig())
    path = cap.save()
    active = WindowManager.active()
    lines = [f"Screen: {active}", f"Screenshot: {path}"]
    if elements:
        for el in elements[:35]:
            lines.append(f"  '{el['text']}' at ({el['center'][0]},{el['center'][1]})")
    else:
        lines.append("  (no text detected)")
    return "\n".join(lines)


async def find_ui_element(text: str = "", region: str = "", skip_chrome: bool = False) -> str:
    """Find a UI element by its text label using OCR. Returns coordinates.
    region: 'top%,left%,bottom%,right%' to limit search area.
    skip_chrome: True to skip top 8% of screen (browser tabs/address bar).
    """
    if not text:
        return "find_ui_element: provide text"
    r = region or (_CHROME_REGION if skip_chrome else "")
    _, elements = _snapshot(region=r)
    el = _find(elements, text)
    if el:
        return f"Found '{text}' at ({el['center'][0]},{el['center'][1]})"
    return f"'{text}' not visible. Try screenshot() first."


async def click_text(text: str = "", button: str = "left", region: str = "", skip_chrome: bool = False) -> str:
    """Find text on screen via OCR, move mouse, and click.
    region: 'top%,left%,bottom%,right%' to limit search area.
    skip_chrome: True to skip top 8% of screen (browser tabs/address bar).
    """
    if not text:
        return "click_text: provide text to click"
    r = region or (_CHROME_REGION if skip_chrome else "")
    _, elements = _snapshot(region=r)
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


async def double_click_text(text: str = "", region: str = "", skip_chrome: bool = False) -> str:
    """Find text on screen via OCR and double-click.
    region: 'top%,left%,bottom%,right%' to limit search area.
    skip_chrome: True to skip top 8% of screen.
    """
    if not text:
        return "double_click_text: provide text"
    r = region or (_CHROME_REGION if skip_chrome else "")
    _, elements = _snapshot(region=r)
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


async def right_click_text(text: str = "", region: str = "", skip_chrome: bool = False) -> str:
    """Find text on screen via OCR and right-click.
    region: 'top%,left%,bottom%,right%' to limit search area.
    skip_chrome: True to skip top 8% of screen.
    """
    if not text:
        return "right_click_text: provide text"
    r = region or (_CHROME_REGION if skip_chrome else "")
    _, elements = _snapshot(region=r)
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


_FAILSAFE_HELP = "Fail-safe: mouse was at corner. Move it to the center of the screen and retry."


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


def _focus_vscode_hypr():
    """Focus VSCode window on Hyprland via hyprctl."""
    import json
    import subprocess as _sp
    try:
        result = _sp.run(["hyprctl", "-j", "clients"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return False
        clients = json.loads(result.stdout)
        for c in clients:
            cls = c.get("class", "").lower()
            title = c.get("title", "").lower()
            if "code" in cls or "vscode" in title or "visual studio code" in title:
                ws = c["workspace"]["id"]
                _sp.run(["hyprctl", "dispatch", "workspace", str(ws)], timeout=3)
                _sp.run(["hyprctl", "dispatch", "focuswindow", f"class:{c['class']}"], timeout=3)
                return True
    except Exception:
        pass
    return False


def _is_vscode_running() -> bool:
    """Check if VSCode process is already running (cross-platform)."""
    for p in psutil.process_iter(["name"]):
        try:
            pn = p.info.get("name", "").lower()
            if any(x in pn for x in ("code", "vscode")):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def _active_window_is_vscode() -> bool:
    """Check if the foreground window is VSCode."""
    try:
        import pygetwindow as _gw
        active = _gw.getActiveWindow()
        if active:
            t = active.title.lower()
            if any(x in t for x in ("visual studio code", "code -", "code.", "vscode")):
                return True
    except Exception:
        pass
    try:
        import win32gui
        t = win32gui.GetWindowText(win32gui.GetForegroundWindow()).lower()
        if any(x in t for x in ("visual studio code", "code -", "code.", "vscode")):
            return True
    except Exception:
        pass
    return False


def _focus_vscode_win():
    """Focus existing VSCode window on Windows. Tries multiple methods, verifies."""
    import win32con, win32gui, win32process

    # Collect all VSCode window handles first
    targets = []

    def _enum(hwnd, _results):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        t = title.lower()
        if any(x in t for x in ("visual studio code", "code -", "code.", "vscode")):
            _results.append(hwnd)

    win32gui.EnumWindows(_enum, targets)

    if not targets:
        # Fallback: pywinauto by PID
        try:
            from pywinauto import Application as _App
            for p in psutil.process_iter(["name", "pid"]):
                pn = p.info.get("name", "").lower()
                if any(x in pn for x in ("code", "vscode")):
                    _app = _App(backend="uia").connect(process=p.info["pid"])
                    _app.top_window().set_focus()
                    return _active_window_is_vscode()
        except Exception:
            pass
        return False

    # Force foreground via AttachThreadInput (bypasses UIPI)
    import ctypes
    cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()
    for hwnd in targets:
        try:
            tid = win32process.GetWindowThreadProcessId(hwnd)[0]
            win32process.AttachThreadInput(cur_tid, tid, True)
            win32gui.SetForegroundWindow(hwnd)
            win32process.AttachThreadInput(cur_tid, tid, False)
            if _active_window_is_vscode():
                return True
        except Exception:
            continue

    return False


async def write_code(code: str = "", filename: str = "", app: str = "vscode") -> str:
    """Open editor, type code character-by-character (typewriter effect), then save.

    Auto-detects OS. If VSCode is already open, focuses it (Alt+Tab on Windows,
    hyprctl on Hyprland) instead of launching a new window. Then creates a new
    file via Ctrl+N and types the code visibly character-by-character.

    Args:
        code: the full code/content to type (e.g. a complete Python script)
        filename: save as this filename (e.g. 'snake.py', 'index.html'). Default: 'script.py'
        app: editor — 'vscode' (default), 'notepad'
    """
    if not code:
        return "write_code: provide code to write"
    if not filename:
        filename = "script.py"

    existing_path = Path(filename).resolve()
    if existing_path.exists() and existing_path.stat().st_size > 50:
        return (
            f"write_code: '{filename}' already exists ({existing_path.stat().st_size} bytes). "
            f"If this is a bug fix, DO NOT rewrite the whole file. Use read_file('{filename}') "
            f"to check the content, then edit_file(filepath='{filename}', old=..., new=...) "
            f"to make targeted fixes. Only use write_code again if you want a COMPLETE rewrite "
            f"(delete the file first with a run_command)."
        )

    lines = code.split("\n")

    lines = code.split("\n")
    is_linux = sys.platform.startswith("linux")

    try:
        if app in ("vscode", "code"):
            code_running = _is_vscode_running()

            if code_running:
                if is_linux:
                    _focus_vscode_hypr()
                else:
                    _focus_vscode_win()
                    await asyncio.sleep(0.5)
                    if not _active_window_is_vscode():
                        _focus_vscode_win()
                        await asyncio.sleep(0.5)
            else:
                import subprocess as _sp
                if is_linux:
                    try:
                        _sp.Popen(["code"], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
                    except FileNotFoundError:
                        pyautogui.hotkey("win", "enter")
                        await asyncio.sleep(0.5)
                        pyautogui.typewrite("code", interval=0.04)
                        await asyncio.sleep(0.3)
                        pyautogui.press("enter")
                else:
                    pyautogui.hotkey("win")
                    await asyncio.sleep(0.4)
                    pyautogui.typewrite("vscode", interval=0.04)
                    await asyncio.sleep(1.5)
                    pyautogui.press("enter")
            await asyncio.sleep(3.0)

            pyautogui.hotkey("ctrl", "n")
            await asyncio.sleep(1.0)
            pyautogui.hotkey("ctrl", "1")
            await asyncio.sleep(0.5)
            pyautogui.typewrite(code, interval=0.01)
            await asyncio.sleep(0.5)
            pyautogui.hotkey("ctrl", "s")
            await asyncio.sleep(0.5)
            pyautogui.typewrite(filename, interval=0.04)
            await asyncio.sleep(0.3)
            pyautogui.press("enter")

        elif app in ("notepad",):
            if is_linux:
                return "write_code: notepad not available on Linux"
            pyautogui.hotkey("win")
            await asyncio.sleep(0.4)
            pyautogui.typewrite("notepad", interval=0.04)
            await asyncio.sleep(1.5)
            pyautogui.press("enter")
            await asyncio.sleep(1.0)
            pyautogui.typewrite(code, interval=0.01)
            await asyncio.sleep(0.5)
            pyautogui.hotkey("ctrl", "s")
            await asyncio.sleep(0.5)
            pyautogui.typewrite(filename, interval=0.04)
            await asyncio.sleep(0.3)
            pyautogui.press("enter")

        return f"Typewritten {len(lines)} lines to '{filename}' in {app}."

    except pyautogui.FailSafeException:
        return _FAILSAFE_HELP
    except Exception as e:
        return f"write_code error: {e}"


async def search_on_page(query: str = "", region: str = "8,0,100,100") -> str:
    """Find a search bar on the current page, type a query, and submit.

    Uses region filtering to avoid clicking browser chrome elements.
    Works on any website (YouTube, Google, Amazon, Twitter, etc.).

    Args:
        query: text to search for
        region: screen region to look for search bar ('top%,left%,bottom%,right%')
                default '8,0,100,100' skips browser chrome (top 8%).
    """
    if not query:
        return "search_on_page: provide a query"
    try:
        _, elements = _snapshot(region=region)

        search_keywords = ["search", "find", "type here", "look up", "query"]
        search_el = None
        for el in elements:
            if any(kw in el["text"].lower() for kw in search_keywords):
                search_el = el
                break

        if search_el:
            cx, cy = search_el["center"]
            pyautogui.moveTo(cx, cy, duration=0.25)
            pyautogui.click()
            await asyncio.sleep(0.5)
        else:
            x1, y1, x2, y2 = _parse_region(region, (pyautogui.size().width, pyautogui.size().height))
            fallback_x = (x1 + x2) // 2
            fallback_y = y1 + int((y2 - y1) * 0.05)
            pyautogui.moveTo(fallback_x, fallback_y, duration=0.25)
            pyautogui.click()
            await asyncio.sleep(0.5)

        pyautogui.typewrite(query, interval=0.02)
        await asyncio.sleep(0.3)
        pyautogui.press("enter")
        await asyncio.sleep(3)

        img, result_elements = _snapshot(force=True, region=region)
        lines = ["Search submitted. Screen now shows:"]
        for el in result_elements[:30]:
            lines.append(f"  '{el['text']}' at ({el['center'][0]},{el['center'][1]})")
        return "\n".join(lines)
    except pyautogui.FailSafeException:
        return _FAILSAFE_HELP
    except Exception as e:
        return f"search_on_page error: {e}"


async def list_content(region: str = "8,0,100,100", min_chars: int = 3, max_items: int = 20) -> str:
    """Group visible text on screen into content items (search results, lists, cards).
    Groups nearby text elements by proximity. Returns structured items with text and positions.
    Use this after navigating to a page to understand its content structure.

    Args:
        region: screen region ('top%,left%,bottom%,right%'), default skips browser chrome
        min_chars: minimum characters per text element to include
        max_items: maximum number of items to return
    """
    img, elements = _snapshot(region=region)
    if not elements:
        return "(no text detected in region)"

    groups = _group_by_proximity(elements)

    items = []
    for group in groups:
        texts = [g["text"] for g in group if len(g["text"]) >= min_chars]
        if not texts:
            continue
        combined = " | ".join(texts)
        x1 = min(g["bbox"][0] for g in group)
        y1 = min(g["bbox"][1] for g in group)
        x2 = max(g["bbox"][2] for g in group)
        y2 = max(g["bbox"][3] for g in group)
        items.append({
            "text": combined,
            "center": [(x1 + x2) // 2, (y1 + y2) // 2],
            "bbox": [x1, y1, x2, y2],
        })

    if not items:
        return "(no content groups found)"

    lines = [f"Found {len(items)} content items:"]
    for i, item in enumerate(items[:max_items]):
        lines.append(f"  [{i}] \"{item['text'][:150]}\" at ({item['center'][0]},{item['center'][1]})")
    return "\n".join(lines)


async def youtube_search(query: str = "", action: str = "play_first", title_keyword: str = "", result_index: int = 0) -> str:
    """Search YouTube and play a video. High-level: handles navigation, search, result parsing.

    Args:
        query: What to search for (e.g. 'never gonna give you up')
        action: 'play_first' (default) or 'play_by_title'
        title_keyword: If action='play_by_title', play the first result whose title contains this
        result_index: 0-based index to pick from results (default 0)
    """
    if not query:
        return "youtube_search: provide a query"
    try:
        from agent.desktop.config import DesktopConfig
        from agent.desktop.vision import ScreenCapture, OCR, UIDetector
        from agent.desktop.automation import Mouse, Keyboard
        from agent.desktop.browser import BrowserNav, BrowserSearch
        from agent.desktop.workflows import YouTubeWorkflow

        cfg = DesktopConfig()
        mouse = Mouse(cfg)
        keyboard = Keyboard(cfg)
        capture = ScreenCapture(cfg)
        ocr = OCR(cfg)
        detector = UIDetector(cfg, capture, ocr)
        nav = BrowserNav(cfg, mouse, keyboard, detector)
        browser_search = BrowserSearch(cfg, mouse, keyboard, detector)

        yt = YouTubeWorkflow(cfg, mouse, keyboard, detector, nav, browser_search)

        if action == "play_by_title" and title_keyword:
            result = yt.search_and_play(query, title_keyword=title_keyword)
        else:
            result = yt.search_and_play(query, result_index=result_index)

        return result
    except Exception as e:
        return f"youtube_search error: {e}"


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
    "search_on_page": search_on_page,
    "list_content": list_content,
    "write_code": write_code,
    "edit_file": edit_file,
    "youtube_search": youtube_search,
}
