"""Execution state — tracks plan progress, step results, retries."""

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Step:
    index: int
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    success: Optional[bool] = None
    result: str = ""
    retries: int = 0
    screenshot: str = ""
    timestamp: float = 0.0


class ExecutionState:
    def __init__(self, task: str):
        self.task = task
        self.steps: list[Step] = []
        self.current_index: int = 0
        self.failures: int = 0
        self.max_retries: int = 3
        self.max_failures: int = 5
        self.start_time = time.time()
        self.completed = False
        self.final_result: str = ""

    def add_step(self, action: str, params: dict, desc: str = "") -> Step:
        step = Step(
            index=len(self.steps) + 1,
            action=action,
            params=params,
            description=desc,
        )
        self.steps.append(step)
        return step

    def current_step(self) -> Optional[Step]:
        if 0 <= self.current_index < len(self.steps):
            return self.steps[self.current_index]
        return None

    def mark_success(self, result: str = "", screenshot: str = ""):
        step = self.current_step()
        if step:
            step.success = True
            step.result = result
            step.screenshot = screenshot
            step.timestamp = time.time()
        self.current_index += 1
        self.failures = 0

    def mark_failure(self, reason: str = ""):
        step = self.current_step()
        if step:
            step.success = False
            step.result = reason
            step.retries += 1
            step.timestamp = time.time()
            self.failures += 1

    @property
    def should_retry(self) -> bool:
        step = self.current_step()
        if step and step.retries < self.max_retries:
            return True
        return False

    @property
    def should_abort(self) -> bool:
        return self.failures >= self.max_failures

    @property
    def is_done(self) -> bool:
        return self.current_index >= len(self.steps) or self.should_abort

    @property
    def progress(self) -> str:
        total = len(self.steps)
        done = sum(1 for s in self.steps if s.success is True)
        failed = sum(1 for s in self.steps if s.success is False)
        return f"{done}/{total} (fail={failed})"

    def summary(self) -> str:
        lines = [f"Task: {self.task}", f"Progress: {self.progress}"]
        for s in self.steps:
            status = "OK" if s.success else ("FAIL" if s.success is False else "PEND")
            lines.append(f"  [{status}] {s.action} {s.params} -> {s.result[:60]}")
        return "\n".join(lines)
