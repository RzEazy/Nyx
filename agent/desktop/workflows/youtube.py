"""YouTube workflow — search videos, parse results with metadata, play the right one."""

import time

from ..config import DesktopConfig
from ..automation import Mouse, Keyboard
from ..vision import UIDetector, ScreenCapture, OCR
from ..browser import BrowserNav, BrowserSearch
from ..utils import get_logger

log = get_logger("workflows.youtube")


class YouTubeWorkflow:
    def __init__(self, cfg: DesktopConfig, mouse: Mouse, keyboard: Keyboard,
                 detector: UIDetector, nav: BrowserNav, search: BrowserSearch):
        self.cfg = cfg
        self.mouse = mouse
        self.keyboard = keyboard
        self.detector = detector
        self.nav = nav
        self.search = search
        self._capture = ScreenCapture(cfg)
        self._ocr = OCR(cfg)

    def search_and_play(self, query: str, title_keyword: str = "", result_index: int = 0) -> str:
        """Full pipeline: YouTube → search → pick video → play. Returns result description."""
        log.info("YouTube: search '%s', index=%s, title='%s'", query, result_index, title_keyword)

        self.nav.go_to_and_wait("youtube.com", 3)
        self._save("home")

        bar = self._find_search_bar()
        if bar:
            self.mouse.click_element(bar)
            log.info("Clicked YouTube search bar at %s", bar["center"])
        else:
            img = self._capture.capture()
            w, h = img.size
            self.mouse.click(w // 2, int(h * 0.08))
            log.info("Fallback: clicked center-top")
        time.sleep(0.5)

        self.keyboard.type(query, interval=0.03)
        self.keyboard.press("enter")
        time.sleep(3)
        self._save("results")

        results = self._parse_results()
        if not results:
            return "FAILED: No search results found."

        summary_lines = []
        for i, r in enumerate(results[:10]):
            title = r.get("title", r.get("text", "?"))
            channel = r.get("channel", "")
            meta = r.get("metadata", "")
            summary_lines.append(f"  [{i}] \"{title}\"  {channel}  {meta}".strip())
        summary = "YouTube results:\n" + "\n".join(summary_lines)

        target = None
        if title_keyword:
            for r in results:
                if title_keyword.lower() in r.get("title", "").lower():
                    target = r
                    break

        if not target and result_index < len(results):
            target = results[result_index]

        if not target:
            return summary + "\n\nFAILED: Could not pick a video."

        self.mouse.click_element(target)
        time.sleep(3)
        self._save("playing")

        title = target.get("title", target.get("text", "video"))[:60]
        log.info("Now playing: %s", title)
        return f"Playing: {title}\n\n{summary}"

    def _find_search_bar(self) -> dict | None:
        """Find YouTube search bar using region heuristics.

        YouTube's search bar is in the content area (below browser chrome),
        centered horizontally with 'Search' placeholder text.
        """
        img = self._capture.capture()
        w, h = img.size
        elements = self._ocr.detect(img)

        y_top = int(h * 0.06)
        y_bot = int(h * 0.20)
        x_left = int(w * 0.15)
        x_right = int(w * 0.85)

        candidates = []
        for el in elements:
            _, ey, _, ey2 = el["bbox"]
            if not (y_top <= ey <= y_bot or y_top <= ey2 <= y_bot):
                continue
            cx = el["center"][0]
            if not (x_left <= cx <= x_right):
                continue
            if "search" in el["text"].lower():
                candidates.append(el)
        if candidates:
            return max(candidates, key=lambda x: x["bbox"][2] - x["bbox"][0])

        for el in elements:
            _, ey, _, ey2 = el["bbox"]
            ew = el["bbox"][2] - el["bbox"][0]
            if ew > 300 and y_top <= ey <= y_bot and x_left <= el["center"][0] <= x_right:
                candidates.append(el)
        if candidates:
            return max(candidates, key=lambda x: x["bbox"][2] - x["bbox"][0])

        return None

    def _parse_results(self) -> list[dict]:
        """Parse YouTube search results into structured list with metadata.

        Returns list of {title, channel, metadata, center, bbox, confidence}
        where metadata is the view count / upload date line.
        """
        img = self._capture.capture()
        w, h = img.size
        elements = self._ocr.detect(img)

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

        scored = []
        for group in groups:
            if not group:
                continue
            texts = [g["text"] for g in group]
            combined = " ".join(texts).lower()

            nav_keywords = ["home", "trending", "subscriptions", "library", "history", "youtube"]
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
                                            "minute", "second", "views", "subscriber",
                                            "recommended", "premier"]):
                    metadata = t
                elif t != title and 3 < len(t) < 40 and "@" not in tl:
                    if not any(kw in tl for kw in ["youtube", "search", "filter", "sort"]):
                        channel = t

            x1 = min(g["bbox"][0] for g in group)
            y1 = min(g["bbox"][1] for g in group)
            x2 = max(g["bbox"][2] for g in group)
            y2 = max(g["bbox"][3] for g in group)

            scored.append({
                "title": title,
                "channel": channel,
                "metadata": metadata,
                "text": title,
                "center": [(x1 + x2) // 2, (y1 + y2) // 2],
                "bbox": [x1, y1, x2, y2],
                "confidence": max(g["confidence"] for g in group),
            })

        scored.sort(key=lambda x: x["center"][1])
        return scored[:15]

    def _save(self, tag: str) -> str:
        try:
            return self._capture.save(f"yt_{tag}")
        except Exception:
            return ""
