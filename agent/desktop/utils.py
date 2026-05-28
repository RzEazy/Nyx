"""Shared utilities."""

import logging
import sys
import time
from pathlib import Path


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"desktop.{name}")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        logger.addHandler(h)
    return logger


def ensure_dir(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


class Safety:
    def __init__(self, cfg):
        self.cfg = cfg
        self.failures = 0
        self.start = time.time()
        self.aborted = False

    def ok(self):
        self.failures = 0

    def fail(self) -> bool:
        self.failures += 1
        return self.failures >= self.cfg.max_failures

    @property
    def elapsed(self) -> float:
        return time.time() - self.start
