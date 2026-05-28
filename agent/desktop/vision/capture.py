"""Fast screen capture using MSS."""

from pathlib import Path

from ..config import DesktopConfig
from ..utils import ensure_dir, get_logger

log = get_logger("vision.capture")

HAS_MSS = False
try:
    import mss
    HAS_MSS = True
except ImportError:
    pass


class ScreenCapture:
    def __init__(self, cfg: DesktopConfig):
        self.cfg = cfg
        self._dir = ensure_dir(cfg.screenshot_dir)

    def capture(self):
        from PIL import Image
        if HAS_MSS:
            with mss.mss() as sct:
                mon = sct.monitors[0]
                raw = sct.grab(mon)
                return Image.frombytes("RGB", raw.size, raw.rgb)
        from PIL import ImageGrab
        return ImageGrab.grab()

    def save(self, tag: str = "screen") -> str:
        img = self.capture()
        import time
        ts = int(time.time() * 1000)
        path = str(self._dir / f"{tag}_{ts}.png")
        img.save(path)
        return path

    def resolution(self) -> tuple[int, int]:
        img = self.capture()
        return img.width, img.height
