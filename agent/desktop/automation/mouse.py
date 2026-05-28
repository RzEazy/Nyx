"""Mouse control via PyAutoGUI."""

import pyautogui

from ..config import DesktopConfig
from ..utils import get_logger

log = get_logger("automation.mouse")


class Mouse:
    def __init__(self, cfg: DesktopConfig):
        self.cfg = cfg
        pyautogui.FAILSAFE = cfg.failsafe_enabled
        pyautogui.PAUSE = cfg.action_delay

    def position(self) -> tuple[int, int]:
        p = pyautogui.position()
        return p.x, p.y

    def move(self, x: int, y: int, duration: float = 0.3):
        pyautogui.moveTo(int(x), int(y), duration=duration)

    def click(self, x: int | None = None, y: int | None = None, button: str = "left"):
        if x is not None and y is not None:
            pyautogui.click(int(x), int(y), button=button)
        else:
            pyautogui.click(button=button)

    def double_click(self, x: int | None = None, y: int | None = None):
        if x is not None and y is not None:
            pyautogui.doubleClick(int(x), int(y))
        else:
            pyautogui.doubleClick()

    def right_click(self, x: int | None = None, y: int | None = None):
        if x is not None and y is not None:
            pyautogui.rightClick(int(x), int(y))
        else:
            pyautogui.rightClick()

    def drag(self, sx: int, sy: int, ex: int, ey: int, duration: float = 0.5, button: str = "left"):
        pyautogui.moveTo(int(sx), int(sy), duration=0.1)
        pyautogui.drag(int(ex - sx), int(ey - sy), duration=duration, button=button)

    def scroll(self, amount: int = -3):
        pyautogui.scroll(amount)

    def click_element(self, element: dict):
        """Click center of a detected UI element."""
        cx, cy = element["center"]
        self.click(cx, cy)
        return cx, cy
