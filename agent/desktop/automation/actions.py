"""Action registry — maps action names to implementation functions."""

import time as _time

from ..config import DesktopConfig
from ..utils import get_logger
from .mouse import Mouse
from .keyboard import Keyboard

log = get_logger("automation.actions")


class ActionRegistry:
    def __init__(self, cfg: DesktopConfig):
        self.cfg = cfg
        self.mouse = Mouse(cfg)
        self.keyboard = Keyboard(cfg)
        self._registry = self._build()

    def _build(self) -> dict:
        return {
            "move_mouse": lambda p: self.mouse.move(p.get("x"), p.get("y"), p.get("duration", 0.3)),
            "click": lambda p: self.mouse.click(p.get("x"), p.get("y"), p.get("button", "left")),
            "double_click": lambda p: self.mouse.double_click(p.get("x"), p.get("y")),
            "right_click": lambda p: self.mouse.right_click(p.get("x"), p.get("y")),
            "drag": lambda p: self.mouse.drag(p["start_x"], p["start_y"], p["end_x"], p["end_y"]),
            "scroll": lambda p: self.mouse.scroll(p.get("amount", -3)),
            "type_text": lambda p: self.keyboard.type(p.get("text", p.get("value", "")), p.get("interval", 0.02)),
            "press_key": lambda p: self.keyboard.press(p["key"], p.get("count", 1)),
            "hotkey": lambda p: self.keyboard.combo(p.get("keys", [])),
            "wait": lambda p: _time.sleep(p.get("seconds", 1)),
            "mouse_position": lambda p: self.mouse.position(),
        }

    def execute(self, name: str, params: dict) -> tuple[bool, str]:
        fn = self._registry.get(name)
        if fn is None:
            return False, f"Unknown action: {name}"
        try:
            result = fn(params)
            if result is None:
                result = "ok"
            return True, str(result)
        except Exception as e:
            return False, f"{name} failed: {e}"


ACTION_REGISTRY: ActionRegistry = None
_config_global = None


def init(cfg: DesktopConfig):
    global ACTION_REGISTRY, _config_global
    _config_global = cfg
    ACTION_REGISTRY = ActionRegistry(cfg)


def execute(name: str, params: dict) -> tuple[bool, str]:
    global ACTION_REGISTRY
    if ACTION_REGISTRY is None:
        init(DesktopConfig())
    return ACTION_REGISTRY.execute(name, params)
