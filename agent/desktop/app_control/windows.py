"""Window detection, focus, and management via pygetwindow."""

from typing import Optional

import pygetwindow as gw

from ..utils import get_logger

log = get_logger("app_control.windows")


class WindowManager:
    @staticmethod
    def active() -> str:
        try:
            w = gw.getActiveWindow()
            return w.title if w else ""
        except Exception:
            return ""

    @staticmethod
    def list_all() -> list[str]:
        try:
            return [w.title for w in gw.getWindowsWithTitle("") if w.title.strip()]
        except Exception:
            return []

    @staticmethod
    def find(title_contains: str) -> Optional[object]:
        title_contains = title_contains.lower()
        try:
            for w in gw.getWindowsWithTitle(""):
                if title_contains in w.title.lower() and w.title.strip():
                    return w
        except Exception:
            pass
        return None

    @staticmethod
    def focus(title_contains: str) -> bool:
        w = WindowManager.find(title_contains)
        if w is None:
            return False
        try:
            if w.isMinimized:
                w.restore()
            w.activate()
            return True
        except Exception:
            return False

    @staticmethod
    def switch_to_browser() -> bool:
        for name in ("chrome", "edge", "firefox", "opera", "brave"):
            if WindowManager.focus(name):
                return True
        return False

    @staticmethod
    def focus_or_launch(app_name: str) -> str:
        """Try to focus existing window; if not found, return 'launch'."""
        if WindowManager.focus(app_name):
            return f"Focused existing {app_name} window"
        return f"launch:{app_name}"

    @staticmethod
    def is_open(title_contains: str) -> bool:
        return WindowManager.find(title_contains) is not None
