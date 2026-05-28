"""Application launcher via Win key search and direct execution."""

import subprocess
import sys

import pyautogui
import time

from ..config import DesktopConfig
from ..utils import get_logger

log = get_logger("app_control.launcher")


class Launcher:
    def __init__(self, cfg: DesktopConfig):
        self.cfg = cfg

    def via_search(self, query: str):
        """Win key → type query → Enter."""
        pyautogui.hotkey("win")
        time.sleep(0.4)
        pyautogui.typewrite(query, interval=0.04)
        time.sleep(1.2)
        pyautogui.press("enter")
        log.info("Launched via search: %s", query)

    def via_cmd(self, command: str):
        """Direct subprocess launch (fallback)."""
        try:
            if sys.platform == "win32":
                subprocess.Popen(command, shell=True, start_new_session=True)
            else:
                subprocess.Popen([command], start_new_session=True)
            log.info("Launched via cmd: %s", command)
        except Exception as e:
            log.error("Launch failed: %s", e)

    def chrome(self):
        if sys.platform == "win32":
            self.via_cmd("start chrome")
        else:
            self.via_cmd("google-chrome")

    def notepad(self):
        self.via_search("notepad")

    def vscode(self):
        self.via_search("vs code")

    def calculator(self):
        self.via_search("calculator")
