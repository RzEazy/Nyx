"""LLM integration — Cohere Command A."""

from typing import Optional

import cohere
from dotenv import load_dotenv
import os

from .config import DesktopConfig
from .utils import get_logger

log = get_logger("brain")


class Brain:
    def __init__(self, cfg: DesktopConfig):
        self.cfg = cfg
        self._client: Optional[cohere.Client] = None

    def _client_get(self) -> cohere.Client:
        if self._client is None:
            load_dotenv()
            key = os.getenv("COHERE_API_KEY", "")
            if not key:
                from agent.config import get_settings
                key = get_settings().cohere_api_key
            self._client = cohere.Client(key)
        return self._client

    async def think(self, prompt: str) -> str:
        try:
            resp = self._client_get().chat(
                model=self.cfg.model,
                message=prompt,
                temperature=self.cfg.temperature,
            )
            return resp.text.strip()
        except Exception as e:
            log.error("Cohere error: %s", e)
            return ""
