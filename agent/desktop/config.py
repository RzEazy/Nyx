"""Configuration."""

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class DesktopConfig:
    # LLM
    provider: Literal["cohere", "openai", "anthropic"] = "cohere"
    model: str = "command-a-03-2025"
    temperature: float = 0.0

    # Timing
    action_delay: float = 0.3
    type_interval: float = 0.03
    wait_after_action: float = 0.6

    # Agent loop
    max_iterations: int = 40
    max_retries: int = 3
    max_failures: int = 6

    # OCR
    ocr_confidence: float = 0.3
    ocr_languages: list[str] = field(default_factory=lambda: ["en"])

    # Vision
    screenshot_dir: str = "./data/desktop_screenshots"
    template_dir: str = "./data/templates"
    use_template_matching: bool = True
    ui_confidence: float = 0.7

    # Safety
    failsafe_enabled: bool = True
    action_timeout: float = 20.0

    # Browser
    default_browser: str = "chrome"
    url_shortcut: str = "ctrl+l"

    # Memory
    max_session_memory: int = 50
    coordinate_expiry: int = 300
