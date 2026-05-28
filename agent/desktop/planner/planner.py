"""Planner — converts natural language tasks into structured step lists."""

import json
import re

from ..config import DesktopConfig
from ..brain import Brain
from ..utils import get_logger

log = get_logger("planner")

PLANNER_PROMPT = """You are a desktop automation planner. Convert the user's task into a step-by-step plan.

Each step must be an object with:
  "action": one of the action names below
  "params": parameters for the action
  "description": what this step does in plain English

Available actions:
- press_key(key) — press a key: win, enter, tab, escape, f6, ctrl, etc.
- hotkey(keys=[...]) — key combo: ["ctrl","l"], ["win","d"], ["alt","tab"]
- type_text(text) — type text at cursor
- click(x,y) — click coordinates (use from screen detection, not hardcoded)
- scroll(amount) — positive=up, negative=down
- wait(seconds) — pause execution
- screenshot() — capture screen state
- detect_element(text) — find UI element by text and return its position

Rules:
1. Break tasks into smallest possible steps
2. Always check if app is running first
3. For browser tasks: Win key → type browser → Enter → Ctrl+L → URL → Enter
4. Add wait() after launching apps and loading pages
5. Add screenshot() after critical actions to verify state
6. Use detect_element() to find UI elements dynamically instead of coordinates
7. Never use hardcoded coordinates for dynamic elements

Return ONLY a JSON array. No markdown fences, no commentary.
"""


class Planner:
    def __init__(self, cfg: DesktopConfig, brain: Brain):
        self.cfg = cfg
        self.brain = brain

    async def plan(self, task: str, context: str = "") -> list[dict]:
        prompt = PLANNER_PROMPT
        if context:
            prompt += f"\nCurrent screen state:\n{context}\n"
        prompt += f'\nTask: "{task}"\nSteps:\n'

        try:
            raw = await self.brain.think(prompt)
            return self._parse(raw)
        except Exception as e:
            log.warning("LLM plan failed: %s", e)
            return self._fallback(task)

    def _parse(self, raw: str) -> list[dict]:
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
        start = raw.find("[")
        end = raw.rfind("]")
        if start >= 0 and end > start:
            raw = raw[start:end + 1]
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
        return []

    def _fallback(self, task: str) -> list[dict]:
        t = task.lower()
        steps = []

        if "instagram" in t and "dm" in t and "message" in t:
            steps = [
                {"action": "app_check", "params": {"app": "chrome"}, "description": "Check if Chrome is running"},
                {"action": "hotkey", "params": {"keys": ["ctrl", "l"]}, "description": "Focus address bar"},
                {"action": "type_text", "params": {"text": "instagram.com"}, "description": "Type Instagram URL"},
                {"action": "press_key", "params": {"key": "enter"}, "description": "Navigate to Instagram"},
                {"action": "wait", "params": {"seconds": 4}, "description": "Wait for Instagram to load"},
                {"action": "screenshot", "params": {}, "description": "Check Instagram state"},
            ]
        elif "youtube" in t:
            steps = [
                {"action": "app_check", "params": {"app": "chrome"}, "description": "Check Chrome"},
                {"action": "hotkey", "params": {"keys": ["ctrl", "l"]}, "description": "Focus address bar"},
                {"action": "type_text", "params": {"text": "youtube.com"}, "description": "Type YouTube URL"},
                {"action": "press_key", "params": {"key": "enter"}, "description": "Go to YouTube"},
                {"action": "wait", "params": {"seconds": 3}, "description": "Wait for YouTube"},
                {"action": "screenshot", "params": {}, "description": "Check YouTube loaded"},
            ]
        elif "chrome" in t:
            steps = [
                {"action": "app_check", "params": {"app": "chrome"}, "description": "Check if Chrome is running"},
                {"action": "press_key", "params": {"key": "win"}, "description": "Open Start menu"},
                {"action": "wait", "params": {"seconds": 0.5}, "description": "Wait for Start menu"},
                {"action": "type_text", "params": {"text": "chrome"}, "description": "Search for Chrome"},
                {"action": "press_key", "params": {"key": "enter"}, "description": "Open Chrome"},
                {"action": "wait", "params": {"seconds": 2}, "description": "Wait for Chrome"},
                {"action": "screenshot", "params": {}, "description": "Verify Chrome opened"},
            ]
        else:
            steps = [
                {"action": "screenshot", "params": {}, "description": "Assess current screen state"},
            ]

        if "search" in t or "find" in t:
            for s in steps:
                if s["action"] == "screenshot":
                    break
            else:
                steps.append({"action": "detect_element", "params": {"text": "search"}, "description": "Find search bar"})

        return steps
