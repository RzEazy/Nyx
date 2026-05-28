"""Keyboard control via PyAutoGUI."""

import pyautogui

from ..config import DesktopConfig
from ..utils import get_logger

log = get_logger("automation.keyboard")


class Keyboard:
    def __init__(self, cfg: DesktopConfig):
        self.cfg = cfg
        pyautogui.PAUSE = cfg.action_delay

    def type(self, text: str, interval: float = 0.02):
        pyautogui.typewrite(text, interval=interval)

    def press(self, key: str, count: int = 1):
        for _ in range(count):
            pyautogui.press(key.lower())

    def hotkey(self, *keys: str):
        pyautogui.hotkey(*keys)

    def combo(self, keys: list[str]):
        pyautogui.hotkey(*keys)
