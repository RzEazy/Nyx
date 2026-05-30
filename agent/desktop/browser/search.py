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

    def find_search_bar(self, region: tuple = None) -> dict | None:
        """Find a search bar on the current page.

        Args:
            region: Optional (top, bottom, left, right) as fractions of screen size.
                    e.g. (0.06, 0.22, 0.15, 0.85) for YouTube's search bar area.
        """
        if region:
            img = self.detector._cap.capture()
            w, h = img.size
            results = self.detector._ocr.detect(img)
            y_top, y_bot, x_left, x_right = (
                int(h * region[0]), int(h * region[1]),
                int(w * region[2]), int(w * region[3]),
            )
            for el in results:
                _, ey, _, ey2 = el["bbox"]
                if not (y_top <= ey <= y_bot or y_top <= ey2 <= y_bot):
                    continue
                cx = el["center"][0]
                if not (x_left <= cx <= x_right):
                    continue
                if "search" in el["text"].lower():
                    return el
            for el in results:
                _, ey, _, ey2 = el["bbox"]
                ew = el["bbox"][2] - el["bbox"][0]
                if ew > 300 and y_top <= ey <= y_bot and x_left <= el["center"][0] <= x_right:
                    return el
            return None
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
        """Detect search result links/thumbnails on the current page.

        Groups nearby text elements into result cards and parses metadata
        like view counts, upload dates, and channel names.
        """
        img = self.detector._cap.capture()
        w, h = img.size
        elements = self.detector._ocr.detect(img)

        results_area = [el for el in elements if el["center"][1] > h * 0.18]
        results_area.sort(key=lambda x: (x["center"][1], x["center"][0]))

        groups = []
        cur = []
        last_y = -100
        for el in results_area:
            cy = el["center"][1]
            if cur and cy - last_y > 45:
                groups.append(cur)
                cur = []
            cur.append(el)
            last_y = cy
        if cur:
            groups.append(cur)

        candidates = []
        for group in groups:
            if not group:
                continue
            texts = [g["text"] for g in group]
            combined = " ".join(texts).lower()

            nav_keywords = ["home", "trending", "subscriptions", "library", "history"]
            if any(kw in combined for kw in nav_keywords):
                long = [t for t in texts if len(t) > 6]
                if len(long) < 2:
                    continue

            long_texts = [t for t in texts if len(t) > 10 and " " in t]
            title = long_texts[0] if long_texts else (group[0]["text"] if group else "?")
            channel = ""
            metadata = ""

            for t in texts:
                tl = t.lower()
                if any(kw in tl for kw in ["ago", "year", "month", "week", "day", "hour",
                                            "minute", "second", "views", "subscriber"]):
                    metadata = t
                elif t != title and 3 < len(t) < 40:
                    if not any(kw in tl for kw in ["youtube", "search", "filter", "sort"]):
                        channel = t

            x1 = min(g["bbox"][0] for g in group)
            y1 = min(g["bbox"][1] for g in group)
            x2 = max(g["bbox"][2] for g in group)
            y2 = max(g["bbox"][3] for g in group)

            candidates.append({
                "title": title,
                "channel": channel,
                "metadata": metadata,
                "text": title,
                "center": [group[0]["center"][0], (y1 + y2) // 2],
                "bbox": [x1, y1, x2, y2],
                "confidence": max(g["confidence"] for g in group),
            })

        candidates.sort(key=lambda x: x["center"][1])
        return candidates[:15]

    def open_first_result(self):
        results = self.detect_search_results()
        if results:
            self.mouse.click_element(results[0])
            log.info("Opened first result: %s", results[0].get("title", results[0]["text"])[:60])
            time.sleep(2)
            return True
        log.warning("No search results detected")
        return False

    def open_result_by_index(self, index: int = 0):
        results = self.detect_search_results()
        if index < len(results):
            self.mouse.click_element(results[index])
            log.info("Opened result %d: %s", index, results[index].get("title", results[index]["text"])[:60])
            time.sleep(2)
            return True
        return False
