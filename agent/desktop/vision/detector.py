"""UI element detection — finds buttons, search bars, inputs, tabs on screen."""

from typing import Optional

from ..config import DesktopConfig
from ..utils import get_logger
from .capture import ScreenCapture
from .ocr import OCR

log = get_logger("vision.detector")

try:
    import cv2
    import numpy as np
    HAS_CV = True
except ImportError:
    HAS_CV = False


class UIDetector:
    def __init__(self, cfg: DesktopConfig, capture: ScreenCapture, ocr: OCR):
        self.cfg = cfg
        self._cap = capture
        self._ocr = ocr
        self._last_image = None

    # ── high-level ──────────────────────────────────────────────────

    def find_text(self, query: str):
        """Find text on current screen."""
        img = self._cap.capture()
        self._last_image = img
        return self._ocr.find(img, query)

    def find_any(self, queries: list[str]):
        img = self._cap.capture()
        self._last_image = img
        return self._ocr.find_any(img, queries)

    def find_all_text(self):
        img = self._cap.capture()
        self._last_image = img
        return self._ocr.detect(img)

    def get_text_summary(self) -> str:
        img = self._cap.capture()
        self._last_image = img
        return self._ocr.text_summary(img)

    def click_center_of(self, element: dict) -> bool:
        """Return clickable center coords of a detected element."""
        return element["center"] if element else None

    # ── specific UI patterns ────────────────────────────────────────

    def find_search_bar(self) -> Optional[dict]:
        """Detect a search bar via OCR keywords and region heuristics."""
        img = self._cap.capture()
        self._last_image = img
        results = self._ocr.detect(img)
        w, h = img.size

        keywords = ["search", "find", "look up", "query", "type here", "input"]
        candidates = []
        for r in results:
            if any(kw in r["text"].lower() for kw in keywords):
                candidates.append(r)

        if candidates:
            return max(candidates, key=lambda x: x["confidence"])

        # Fallback: detect input field via its tall narrow bbox in upper region
        if HAS_CV:
            arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                x, y, cw, ch = cv2.boundingRect(cnt)
                aspect = cw / max(ch, 1)
                if 3 < aspect < 20 and y < h * 0.3 and cw > 200:
                    cx = x + cw // 2
                    cy = y + ch // 2
                    return {"text": "(search field)", "center": [cx, cy], "bbox": [x, y, x + cw, y + ch], "confidence": 0.6}
        return None

    def find_address_bar(self) -> Optional[dict]:
        """Detect browser address bar — usually top region with URL pattern."""
        img = self._cap.capture()
        self._last_image = img
        results = self._ocr.detect(img)

        # Look for URL patterns
        for r in results:
            t = r["text"].lower()
            if t.startswith(("http", "www.", "chrome://", "about:")):
                return r
            if "." in t and " " not in t and len(t) > 5:
                return r

        # Fallback: look for text in top 12% of screen, wide region
        w, h = img.size
        for r in results:
            _, y, _, _ = r["bbox"]
            if y < h * 0.12 and (r["bbox"][2] - r["bbox"][0]) > 200:
                return r
        return None

    def find_button(self, label: str) -> Optional[dict]:
        """Find a button by its text label."""
        return self.find_text(label)

    def find_dm_section(self) -> Optional[dict]:
        """Find Instagram DMs or messaging section."""
        keywords = ["messages", "direct", "inbox", "chats", "dm", "conversation"]
        return self.find_any(keywords)

    def find_input_field(self) -> Optional[dict]:
        """Find a text input field — usually near bottom with placeholder text."""
        img = self._cap.capture()
        self._last_image = img
        results = self._ocr.detect(img)
        w, h = img.size

        keywords = ["message", "type", "write", "send", "input", "reply"]
        for r in results:
            if any(kw in r["text"].lower() for kw in keywords):
                return r

        if HAS_CV:
            arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                x, y, cw, ch = cv2.boundingRect(cnt)
                if ch > 30 and cw > 200 and y > h * 0.6:
                    cx = x + cw // 2
                    cy = y + ch // 2
                    return {"text": "(input field)", "center": [cx, cy], "bbox": [x, y, x + cw, y + ch], "confidence": 0.5}
        return None

    def find_tab(self, name: str) -> Optional[dict]:
        """Find a browser tab by its title text."""
        return self.find_text(name)

    def verify_element(self, text: str, timeout: float = 3.0) -> bool:
        """Poll screen until element appears or timeout."""
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.find_text(text):
                return True
        return False
