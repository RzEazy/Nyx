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
