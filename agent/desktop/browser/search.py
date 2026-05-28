"""Browser search — find and interact with search bars, submit queries."""

import time

from ..config import DesktopConfig
from ..automation import Mouse, Keyboard
from ..vision import UIDetector
from ..utils import get_logger

log = get_logger("browser.search")


class BrowserSearch:
    def __init__(self, cfg: DesktopConfig, mouse: Mouse, keyboard: Keyboard, detector: UIDetector):
        self.cfg = cfg
        self.mouse = mouse
        self.keyboard = keyboard
        self.detector = detector

    def find_search_bar(self) -> dict | None:
        return self.detector.find_search_bar()

    def search(self, query: str):
        bar = self.find_search_bar()
        if bar:
            self.mouse.click_element(bar)
            log.info("Clicked search bar at %s", bar["center"])
        else:
            self.keyboard.hotkey("ctrl", "l")
            log.info("Fell back to address bar")
        time.sleep(0.3)
        self.keyboard.type(query, interval=0.03)
        self.keyboard.press("enter")
        log.info("Searched: %s", query)

    def search_on_site(self, site_url: str, query: str, wait: float = 3.0):
        """Navigate to a website and type a search query."""
        from .navigation import BrowserNav
        nav = BrowserNav(self.cfg, self.mouse, self.keyboard, self.detector)
        nav.go_to_and_wait(site_url, wait)
        self.search(query)

    def detect_search_results(self) -> list[dict]:
        """Detect search result links/thumbnails on the current page."""
        results = self.detector.find_all_text()
        # Filter: look for clickable-looking elements (short text, title-like)
        candidates = [r for r in results if len(r["text"]) > 10 and " " in r["text"].strip()]
        return candidates[:10]

    def open_first_result(self):
        results = self.detect_search_results()
        if results:
            self.mouse.click_element(results[0])
            log.info("Opened first result: %s", results[0]["text"][:60])
            time.sleep(2)
            return True
        log.warning("No search results detected")
        return False

    def open_result_by_index(self, index: int = 0):
        results = self.detect_search_results()
        if index < len(results):
            self.mouse.click_element(results[index])
            log.info("Opened result %d: %s", index, results[index]["text"][:60])
            time.sleep(2)
            return True
        return False
