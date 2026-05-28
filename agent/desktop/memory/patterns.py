"""Pattern memory — learns and remembers UI element locations across sessions."""

import json
import time
from pathlib import Path
from typing import Optional

from ..utils import get_logger

log = get_logger("memory.patterns")


class PatternMemory:
    def __init__(self, path: str = "./data/ui_patterns.json"):
        self._path = Path(path)
        self._patterns: dict = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                self._patterns = json.loads(self._path.read_text())
            except Exception:
                self._patterns = {}

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._patterns, indent=2))

    def remember(self, app: str, element: str, x: int, y: int, confidence: float = 0.8):
        key = f"{app.lower()}.{element.lower()}"
        self._patterns[key] = {
            "x": x,
            "y": y,
            "confidence": confidence,
            "updated": time.time(),
        }
        self._save()

    def recall(self, app: str, element: str) -> Optional[dict]:
        key = f"{app.lower()}.{element.lower()}"
        return self._patterns.get(key)

    def get_nearby(self, app: str, element: str, threshold: int = 100) -> Optional[dict]:
        """Recall pattern if it hasn't expired (default coord_expiry seconds)."""
        pat = self.recall(app, element)
        if pat is None:
            return None
        age = time.time() - pat.get("updated", 0)
        if age > 300:
            return None
        return pat

    def clear(self, app: Optional[str] = None):
        if app:
            self._patterns = {k: v for k, v in self._patterns.items() if not k.startswith(app.lower())}
        else:
            self._patterns = {}
        self._save()
