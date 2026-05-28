"""OCR text detection using EasyOCR with confidence scoring."""

import io
from typing import Optional

from ..config import DesktopConfig
from ..utils import get_logger

log = get_logger("vision.ocr")

HAS_EASYOCR = False
try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    pass


class OCR:
    def __init__(self, cfg: DesktopConfig):
        self.cfg = cfg
        self._reader = None

    def _get(self):
        if self._reader is None and HAS_EASYOCR:
            self._reader = easyocr.Reader(self.cfg.ocr_languages, gpu=False, verbose=False)
        return self._reader

    def detect(self, image) -> list[dict]:
        """Run OCR on a PIL Image. Returns list of {text, bbox, center, confidence}."""
        if not HAS_EASYOCR:
            return []
        reader = self._get()
        if reader is None:
            return []

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)

        results = reader.readtext(buf.getvalue())
        out = []
        for bbox, text, conf in results:
            if conf >= self.cfg.ocr_confidence:
                xs = [p[0] for p in bbox]
                ys = [p[1] for p in bbox]
                x_min, x_max = int(min(xs)), int(max(xs))
                y_min, y_max = int(min(ys)), int(max(ys))
                out.append({
                    "text": text.strip(),
                    "bbox": [x_min, y_min, x_max, y_max],
                    "center": [(x_min + x_max) // 2, (y_min + y_max) // 2],
                    "confidence": round(conf, 3),
                })
        return out

    def find(self, image, query: str) -> Optional[dict]:
        """Find first element whose text contains the query (case-insensitive)."""
        q = query.lower().strip()
        for r in self.detect(image):
            if q in r["text"].lower():
                return r
        for r in self.detect(image):
            if any(q == w for w in r["text"].lower().split()):
                return r
        return None

    def find_any(self, image, queries: list[str]) -> Optional[dict]:
        for q in queries:
            found = self.find(image, q)
            if found:
                return found
        return None

    def text_summary(self, image, max_lines: int = 30) -> str:
        lines = []
        for r in self.detect(image):
            lines.append(f"{r['text']}  [{r['center'][0]},{r['center'][1]}]")
        return "\n".join(lines[:max_lines])

    def detect_elements(self, image, keywords: list[str]) -> list[dict]:
        """Find UI elements matching keyword patterns."""
        results = self.detect(image)
        matches = []
        for r in results:
            for kw in keywords:
                if kw.lower() in r["text"].lower():
                    matches.append(r)
                    break
        return matches
