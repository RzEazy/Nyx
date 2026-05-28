"""Session memory — conversation history, action log, screen state."""

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScreenSnapshot:
    text_detected: str = ""
    active_window: str = ""
    windows: list[str] = field(default_factory=list)
    resolution: str = ""
    element_count: int = 0


@dataclass
class ActionRecord:
    action: str
    params: dict
    result: str
    success: bool
    screenshot: str = ""
    timestamp: float = 0.0


class SessionMemory:
    def __init__(self, max_size: int = 50):
        self.max_size = max_size
        self.messages: list[dict] = []
        self.actions: list[ActionRecord] = []
        self.last_screen = ScreenSnapshot()
        self.variables: dict[str, Any] = {}
        self.last_coords: dict[str, list[int]] = {}

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.max_size:
            self.messages.pop(0)

    def add_action(self, action: str, params: dict, result: str, success: bool, screenshot: str = ""):
        rec = ActionRecord(
            action=action,
            params=params,
            result=result,
            success=success,
            screenshot=screenshot,
            timestamp=time.time(),
        )
        self.actions.append(rec)
        if len(self.actions) > self.max_size:
            self.actions.pop(0)

    def save_coord(self, key: str, x: int, y: int):
        self.last_coords[key] = [x, y]

    def get_coord(self, key: str) -> list[int] | None:
        return self.last_coords.get(key)

    def summary(self, recent: int = 5) -> str:
        lines = [f"Active window: {self.last_screen.active_window}"]
        if self.last_screen.text_detected:
            lines.append(f"Screen text: {self.last_screen.text_detected[:200]}")
        recent_actions = self.actions[-recent:]
        if recent_actions:
            lines.append("Recent actions:")
            for a in recent_actions:
                status = "OK" if a.success else "FAIL"
                lines.append(f"  [{status}] {a.action} -> {a.result[:60]}")
        return "\n".join(lines)
