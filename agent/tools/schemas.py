"""Tool names and parameter docs injected into the system prompt."""

TOOL_SPECS: dict[str, dict] = {
    "run_command": {
        "desc": "Run a shell command (10s timeout). Arch Linux: use pacman.",
        "args": {
            "cmd": "shell command string (alias: command); use sudo when needed",
            "background": "optional bool, fire-and-forget",
        },
        "note": "Commands with sudo will prompt the user for their system password in the TUI.",
        "example": {"tool": "run_command", "args": {"cmd": "pacman -Q"}},
    },
    "open_app": {
        "desc": "Launch a GUI app or open file/URL (not run_command).",
        "args": {
            "app": "e.g. firefox, code, spotify (alias: name)",
            "path": "file or folder to open via xdg-open",
            "url": "https://...",
        },
        "example": {"tool": "open_app", "args": {"app": "firefox"}},
    },
    "write_file": {
        "desc": "Write UTF-8 text; creates parent dirs. Relative paths → $HOME.",
        "args": {
            "path": "full file path (or use directory + filename)",
            "directory": "target directory",
            "filename": "file name",
            "content": "text to write",
            "append": "optional bool",
        },
        "example": {
            "tool": "write_file",
            "args": {"path": "~/notes.txt", "content": "hello"},
        },
    },
    "read_file": {
        "desc": "Read a file (max 8KB).",
        "args": {"path": "file path"},
        "example": {"tool": "read_file", "args": {"path": "~/notes.txt"}},
    },
    "list_dir": {
        "desc": "List directory entries.",
        "args": {"path": "directory path"},
        "example": {"tool": "list_dir", "args": {"path": "."}},
    },
    "find_files": {
        "desc": "Glob search under root.",
        "args": {"pattern": "glob e.g. *.py", "root": "directory, default ."},
        "example": {"tool": "find_files", "args": {"pattern": "*.py", "root": "."}},
    },
    "system_info": {
        "desc": "CPU, RAM, disk usage.",
        "args": {},
        "example": {"tool": "system_info", "args": {}},
    },
    "screenshot": {
        "desc": "CAPTURE SCREEN + OCR. Returns all visible text with coordinates. USE THIS FIRST to see what's on screen before clicking anything.",
        "args": {"region": "optional filter: 'top%,left%,bottom%,right%' e.g. '8,0,100,100' skips browser chrome (top 8%)"},
        "note": "Always call this first! It returns UI element positions you can click.",
        "example": {"tool": "screenshot", "args": {}},
    },
    "find_ui_element": {
        "desc": "Find a UI element by its text label using OCR. Returns center coordinates.",
        "args": {
            "text": "text label to find (e.g. 'Chrome', 'Search', 'Send')",
            "region": "optional: 'top%,left%,bottom%,right%' to limit search area",
            "skip_chrome": "True to skip top 8% of screen (browser chrome)",
        },
        "example": {"tool": "find_ui_element", "args": {"text": "Search", "skip_chrome": True}},
    },
    "click_text": {
        "desc": "Find text on screen via OCR, move mouse to it, and click. VISION-GUIDED: no coordinates needed.",
        "args": {
            "text": "visible text to click (e.g. 'Chrome', 'Search', 'Messages')",
            "button": "left (default) or right",
            "region": "optional: 'top%,left%,bottom%,right%' to limit search area",
            "skip_chrome": "True to skip top 8% of screen (browser chrome)",
        },
        "note": "Use skip_chrome=True when clicking page content (avoids clicking browser tabs/address bar).",
        "example": {"tool": "click_text", "args": {"text": "Search", "skip_chrome": True}},
    },
    "double_click_text": {
        "desc": "Find text via OCR and double-click it.",
        "args": {
            "text": "visible text to double-click",
            "region": "optional: 'top%,left%,bottom%,right%' to limit search area",
            "skip_chrome": "True to skip top 8% of screen",
        },
        "example": {"tool": "double_click_text", "args": {"text": "notepad.exe"}},
    },
    "right_click_text": {
        "desc": "Find text via OCR and right-click it.",
        "args": {
            "text": "visible text to right-click",
            "region": "optional: 'top%,left%,bottom%,right%' to limit search area",
            "skip_chrome": "True to skip top 8% of screen",
        },
        "example": {"tool": "right_click_text", "args": {"text": "Desktop"}},
    },
    "mouse_click": {
        "desc": "Click at (x,y) or current position.",
        "args": {
            "x": "optional x coordinate",
            "y": "optional y coordinate",
            "button": "left (default), right, or middle",
        },
        "example": {"tool": "mouse_click", "args": {"x": 500, "y": 300}},
    },
    "mouse_move": {
        "desc": "Move the mouse cursor to (x,y).",
        "args": {"x": "x coordinate", "y": "y coordinate"},
        "example": {"tool": "mouse_move", "args": {"x": 500, "y": 300}},
    },
    "type_text": {
        "desc": "Type text at the current cursor position.",
        "args": {"text": "text to type (alias: value, content)"},
        "example": {"tool": "type_text", "args": {"text": "hello world"}},
    },
    "press_key": {
        "desc": "Press a single key. Common: enter, tab, win, escape, f6, ctrl, alt, shift, up, down.",
        "args": {"key": "key name"},
        "example": {"tool": "press_key", "args": {"key": "win"}},
    },
    "hotkey": {
        "desc": "Press a key combination. Pass as a list of keys.",
        "args": {"keys": "list of key names, e.g. ['ctrl','l'] or string 'ctrl+l'"},
        "example": {"tool": "hotkey", "args": {"keys": ["ctrl", "l"]}},
    },
    "scroll": {
        "desc": "Scroll the mouse wheel. Positive = up, negative = down.",
        "args": {"amount": "integer, default -3"},
        "example": {"tool": "scroll", "args": {"amount": -3}},
    },
    "get_mouse_position": {
        "desc": "Get current mouse cursor coordinates.",
        "args": {},
        "example": {"tool": "get_mouse_position", "args": {}},
    },
    "navigate_to": {
        "desc": "Navigate to a URL in the current browser (Ctrl+L, type URL, Enter).",
        "args": {"url": "the URL to navigate to"},
        "example": {"tool": "navigate_to", "args": {"url": "instagram.com"}},
    },
    "open_app_gui": {
        "desc": "Open a desktop app via Win key search. Use instead of open_app for Windows GUI apps.",
        "args": {"app": "app name to search for (chrome, notepad, calculator, vs code, etc.)"},
        "example": {"tool": "open_app_gui", "args": {"app": "chrome"}},
    },
    "search_on_page": {
        "desc": "Find a search bar on the current page, type a query, and submit. Uses region filtering to avoid browser chrome. Works on ANY website (YouTube, Google, Amazon, Twitter, etc.).",
        "args": {
            "query": "text to search for",
            "region": "screen region to search, default '8,0,100,100' skips top 8% (browser chrome)",
        },
        "note": "PREFER THIS over manually clicking 'Search' + typing for searching on websites.",
        "example": {"tool": "search_on_page", "args": {"query": "lofi hip hop"}},
    },
    "list_content": {
        "desc": "Group visible text into content items by proximity. Parses search results, lists, cards, etc. into structured items you can inspect or click.",
        "args": {
            "region": "screen region, default '8,0,100,100' skips browser chrome",
            "min_chars": "minimum chars per text fragment (default 3)",
            "max_items": "max items to return (default 20)",
        },
        "note": "Use this after search_on_page or navigate_to to understand what's on the page.",
        "example": {"tool": "list_content", "args": {}},
    },
    "write_code": {
        "desc": "Open VSCode via Windows search, create new file, type code character-by-character (typewriter effect) so the user can see it being written, then save. CRITICAL: use this when user asks to 'write code', 'make a program', 'create a script', 'build a webpage'. Do NOT use write_file for code.",
        "args": {
            "code": "the full code/content to type character-by-character",
            "filename": "save as this filename (e.g. 'snake.py', 'hello.py', 'index.html'). Default: 'script.py'",
            "app": "editor: 'vscode' (default), 'notepad'",
        },
        "note": "CRITICAL — ALWAYS use this when user wants code shown. Opens editor, types visibly char-by-char, auto-saves. Do NOT silently write files with write_file.",
        "example": {"tool": "write_code", "args": {"code": "import pygame\n...", "filename": "snake.py"}},
    },
    "edit_file": {
        "desc": "Find and replace text in an existing file. Use for targeted bug fixes instead of rewriting the whole file.",
        "args": {
            "filepath": "path to the file to edit (e.g. 'snake.py')",
            "old": "the exact text to find (must match exactly — include full line with indentation)",
            "new": "the replacement text",
        },
        "note": "PREFER THIS over write_code() when the user reports a bug. Make a single-line fix instead of rewriting.",
        "example": {"tool": "edit_file", "args": {"filepath": "snake.py", "old": "    score = 0", "new": "    score = 0\n    high_score = 0"}},
    },
    "youtube_search": {
        "desc": "HIGH-LEVEL: Search YouTube and play a video in one call. Handles navigation, search bar finding, result parsing (titles/dates/channels), and clicking the video. Use this instead of manually doing navigate_to+click_text+type_text.",
        "args": {
            "query": "search query (e.g. 'never gonna give you up')",
            "action": "'play_first' (default) or 'play_by_title'",
            "title_keyword": "if action='play_by_title', pick first result whose title contains this keyword",
            "result_index": "0-based index of result to play (default 0)",
        },
        "note": "PREFER THIS over manually navigating + clicking for YouTube tasks.",
        "example": {"tool": "youtube_search", "args": {"query": "lofi hip hop mix", "action": "play_first"}},
    },
}


def format_tool_docs() -> str:
    lines = []
    for name, spec in TOOL_SPECS.items():
        lines.append(f"- {name}: {spec['desc']}")
        for arg, hint in spec.get("args", {}).items():
            lines.append(f"    {arg}: {hint}")
        if note := spec.get("note"):
            lines.append(f"    note: {note}")
        lines.append(f"  example: {spec['example']}")
    return "\n".join(lines)
