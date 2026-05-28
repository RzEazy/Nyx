"""Browser navigation — URL entry, tab control, navigation helpers."""

import time

from ..config import DesktopConfig
from ..automation import Mouse, Keyboard
from ..vision import UIDetector
from ..utils import get_logger

log = get_logger("browser.navigation")


class BrowserNav:
    def __init__(self, cfg: DesktopConfig, mouse: Mouse, keyboard: Keyboard, detector: UIDetector):
        self.cfg = cfg
        self.mouse = mouse
        self.keyboard = keyboard
        self.detector = detector

    def focus_address_bar(self):
        self.keyboard.hotkey("ctrl", "l")
        time.sleep(0.3)

    def go_to(self, url: str):
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self.focus_address_bar()
        self.keyboard.type(url, interval=0.03)
        time.sleep(0.2)
        self.keyboard.press("enter")
        log.info("Navigated to: %s", url)

    def go_to_and_wait(self, url: str, wait: float = 3.0):
        self.go_to(url)
        time.sleep(wait)

    def detect_address_bar(self) -> dict | None:
        return self.detector.find_address_bar()

    def click_address_bar(self):
        bar = self.detect_address_bar()
        if bar:
            self.mouse.click_element(bar)
            time.sleep(0.2)
            return True
        self.focus_address_bar()
        return False

    def new_tab(self):
        self.keyboard.hotkey("ctrl", "t")
        time.sleep(0.3)

    def close_tab(self):
        self.keyboard.hotkey("ctrl", "w")

    def switch_tab(self, index: int):
        self.keyboard.hotkey("ctrl", str(index))

    def refresh(self):
        self.keyboard.hotkey("ctrl", "r")

    def back(self):
        self.keyboard.hotkey("alt", "left")

    def forward(self):
        self.keyboard.hotkey("alt", "right")
