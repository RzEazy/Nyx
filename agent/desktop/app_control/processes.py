"""Process detection using psutil."""

import psutil

from ..utils import get_logger

log = get_logger("app_control.processes")

BROWSER_PROCESSES = {"chrome", "msedge", "firefox", "opera", "brave", "vivaldi"}


class ProcessManager:
    @staticmethod
    def is_running(name: str) -> bool:
        name = name.lower()
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] and name in proc.info["name"].lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False

    @staticmethod
    def find_pid(name: str) -> list[int]:
        name = name.lower()
        pids = []
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                if proc.info["name"] and name in proc.info["name"].lower():
                    pids.append(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return pids

    @staticmethod
    def browser_running() -> bool:
        for b in BROWSER_PROCESSES:
            if ProcessManager.is_running(b):
                return True
        return False

    @staticmethod
    def list_all() -> list[dict]:
        procs = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                procs.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return procs

    @staticmethod
    def find_discord() -> bool:
        return ProcessManager.is_running("discord")

    @staticmethod
    def find_chrome() -> bool:
        for name in ("chrome", "googlechrome", "chromium"):
            if ProcessManager.is_running(name):
                return True
        return False
