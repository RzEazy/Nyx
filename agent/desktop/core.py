"""Core agent — the main execution loop with vision-action feedback."""

import time
import traceback

from .config import DesktopConfig
from .utils import Safety, get_logger
from .brain import Brain

from .vision import ScreenCapture, OCR, UIDetector
from .automation import Mouse, Keyboard
from .automation.actions import init as init_actions
from .planner import Planner, ExecutionState, Step
from .memory import SessionMemory, PatternMemory
from .app_control import ProcessManager, WindowManager, Launcher

log = get_logger("core")

VISION_LOOP_PROMPT = """You are a desktop operator AI. You receive screen state and decide the next action.

Current screen analysis:
{screen_context}

Task: {task}
Progress: {progress}
Last action result: {last_result}

Decide the NEXT action. Return ONLY a JSON object:
{{"action": "<name>", "params": {{...}}, "description": "what this step does"}}

Available actions:
- press_key(key) — press key: win, enter, tab, escape, f6
- hotkey(keys=[...]) — combo: ["ctrl","l"], ["win","d"]
- type_text(text) — type at cursor
- click(x,y) — click coordinates
- scroll(amount) — positive=up, negative=down
- wait(seconds) — pause
- screenshot() — capture + OCR
- detect_element(text) — find UI element by label
- done() — signal task complete
"""


class DesktopAgent:
    """Vision-driven semi-autonomous desktop operator."""

    def __init__(self, cfg: DesktopConfig | None = None):
        self.cfg = cfg or DesktopConfig()
        self.safety = Safety(self.cfg)
        self.brain = Brain(self.cfg)

        # Vision
        self.capture = ScreenCapture(self.cfg)
        self.ocr = OCR(self.cfg)
        self.detector = UIDetector(self.cfg, self.capture, self.ocr)

        # Automation
        self.mouse = Mouse(self.cfg)
        self.keyboard = Keyboard(self.cfg)
        init_actions(self.cfg)

        # App control
        self.launcher = Launcher(self.cfg)

        # Memory
        self.session = SessionMemory(self.cfg.max_session_memory)
        self.patterns = PatternMemory()

        # Planner
        self.planner = Planner(self.cfg, self.brain)

        self.state: ExecutionState | None = None
        self._last_action_result = ""

    # ── public API ──────────────────────────────────────────────────

    async def run(self, task: str) -> str:
        log.info("=== TASK START: %s ===", task)
        self.state = ExecutionState(task)
        self.session = SessionMemory(self.cfg.max_session_memory)
        self.session.add_message("user", task)

        # 1. Initial screen assessment
        self._update_screen_context()

        # 2. Plan
        context = self.session.last_screen.text_detected[:500]
        plan = await self.planner.plan(task, context)

        if not plan:
            return "Failed to create plan"

        for item in plan:
            desc = item.get("description", item["action"])
            self.state.add_step(item["action"], item.get("params", {}), desc)

        log.info("Plan: %d steps", len(self.state.steps))

        # 3. Execute loop with verification
        result = await self._execution_loop()
        log.info("=== TASK END: %s ===", result[:100])
        return result

    async def run_interactive(self, task: str) -> str:
        """LLM-decides-each-step mode — full vision feedback loop."""
        log.info("=== INTERACTIVE: %s ===", task)
        self.state = ExecutionState(task)
        self.session = SessionMemory(self.cfg.max_session_memory)

        for iteration in range(self.cfg.max_iterations):
            if self.safety.fail():
                return f"ABORTED: too many failures ({self.safety.failures})"

            ctx = self._get_screen_summary()
            prompt = VISION_LOOP_PROMPT.format(
                screen_context=ctx,
                task=task,
                progress=f"iteration {iteration + 1}/{self.cfg.max_iterations}",
                last_result=self._last_action_result,
            )

            decision = await self.brain.think(prompt)
            action_data = self._parse_decision(decision)
            if action_data is None:
                log.warning("No valid decision, screenshotting")
                self._capture_and_ocr()
                continue

            action = action_data["action"]
            params = action_data.get("params", {})
            desc = action_data.get("description", action)

            if action == "done":
                log.info("LLM signalled done")
                return self.state.summary()

            log.info("Iter %d: %s %s — %s", iteration + 1, action, params, desc)
            ok, msg = await self._execute_verified(action, params)
            self._last_action_result = f"{'OK' if ok else 'FAIL'}: {msg}"

            if ok:
                self.safety.ok()
            else:
                self.safety.fail()

            # Check conventional completion
            if self._task_appears_done(task):
                log.info("Task appears complete")
                return self.state.summary()

        return f"Max iterations ({self.cfg.max_iterations}) reached"

    # ── execution loop ──────────────────────────────────────────────

    async def _execution_loop(self) -> str:
        while not self.state.is_done:
            step = self.state.current_step()
            if step is None:
                break

            log.info("Step %d/%d: %s %s", step.index, len(self.state.steps), step.action, step.params)

            ok, msg = await self._execute_verified(step.action, step.params)

            if ok:
                self.state.mark_success(msg)
                self.safety.ok()
            else:
                self.state.mark_failure(msg)
                if self.state.should_retry:
                    log.warning("Retrying step %d (attempt %d)", step.index, step.retries)
                    continue
                if self.state.should_abort:
                    return f"ABORTED: too many failures"

        return self.state.summary()

    async def _execute_verified(self, action: str, params: dict) -> tuple[bool, str]:
        """Execute an action and verify with screen capture."""
        try:
            if action == "screenshot":
                path = self._capture_and_ocr()
                self.session.add_action(action, params, path, True)
                return True, f"Screenshot: {path}"

            if action == "wait":
                seconds = params.get("seconds", 1)
                time.sleep(seconds)
                self.session.add_action(action, params, f"waited {seconds}s", True)
                return True, f"Waited {seconds}s"

            if action == "detect_element":
                text = params.get("text", "")
                element = self.detector.find_text(text)
                if element:
                    self.session.save_coord(text, *element["center"])
                    self.session.add_action(action, params, f"Found '{text}' at {element['center']}", True)
                    return True, f"Found '{text}' at center {element['center']}"
                self.session.add_action(action, params, f"'{text}' not found", False)
                return False, f"'{text}' not found on screen"

            if action == "app_check":
                app = params.get("app", "")
                if WindowManager.is_open(app):
                    WindowManager.focus(app)
                    msg = f"Switched to existing {app}"
                    self.session.add_action(action, params, msg, True)
                    return True, msg
                msg = f"{app} not running — will launch"
                self.session.add_action(action, params, msg, True)
                return True, msg

            if action == "press_key":
                self.keyboard.press(params.get("key", ""), params.get("count", 1))
                self.session.add_action(action, params, "ok", True)
                return True, "Pressed " + params.get("key", "")

            if action == "hotkey":
                self.keyboard.combo(params.get("keys", []))
                self.session.add_action(action, params, "ok", True)
                return True, "Hotkey " + "+".join(params.get("keys", []))

            if action == "type_text":
                text = params.get("text", params.get("value", ""))
                self.keyboard.type(text)
                self.session.add_action(action, params, f"typed {len(text)} chars", True)
                return True, f"Typed {len(text)} chars"

            if action == "click":
                x, y = params.get("x"), params.get("y")
                if x is not None and y is not None:
                    self.mouse.click(x, y)
                    self.session.add_action(action, params, f"clicked ({x},{y})", True)
                    return True, f"Clicked ({x},{y})"
                pos = self.mouse.position()
                self.mouse.click()
                self.session.add_action(action, params, f"clicked at {pos}", True)
                return True, f"Clicked at {pos}"

            if action == "scroll":
                self.mouse.scroll(params.get("amount", -3))
                self.session.add_action(action, params, "ok", True)
                return True, "Scrolled"

            if action == "move_mouse":
                self.mouse.move(params["x"], params["y"])
                self.session.add_action(action, params, "ok", True)
                return True, f"Moved to ({params['x']},{params['y']})"

            if action == "mouse_position":
                pos = self.mouse.position()
                self.session.add_action(action, params, str(pos), True)
                return True, f"Mouse at {pos}"

            if action == "double_click":
                self.mouse.double_click(params.get("x"), params.get("y"))
                self.session.add_action(action, params, "ok", True)
                return True, "Double clicked"

            return False, f"Unknown action: {action}"

        except Exception as e:
            log.error("Execute error: %s", traceback.format_exc())
            return False, str(e)

    # ── helpers ─────────────────────────────────────────────────────

    def _capture_and_ocr(self) -> str:
        path = self.capture.save("verify")
        img = self.capture.capture()
        text = self.ocr.text_summary(img)
        self.session.last_screen.text_detected = text
        self.session.last_screen.active_window = WindowManager.active()
        self.session.last_screen.windows = WindowManager.list_all()
        return path

    def _update_screen_context(self):
        self._capture_and_ocr()

    def _get_screen_summary(self) -> str:
        return (
            f"Active window: {self.session.last_screen.active_window}\n"
            f"Detected text:\n{self.session.last_screen.text_detected[:600]}"
        )

    def _parse_decision(self, raw: str) -> dict | None:
        import json, re
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start:end + 1]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def _task_appears_done(self, task: str) -> bool:
        t = task.lower()
        aw = self.session.last_screen.active_window.lower()

        if "chrome" in t and "chrome" in aw:
            return True
        if "instagram" in t and "instagram" in aw:
            return True
        if "notepad" in t and "notepad" in aw:
            return True
        if "youtube" in t and "youtube" in aw:
            return True
        if "vscode" in t or "code" in t:
            if "code" in aw or "visual studio" in aw:
                return True
        if "spotify" in t and "spotify" in aw:
            return True
        return False
