from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant" | "system"
    content: str


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[ChatMessage], **kwargs) -> str: ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def supports_streaming(self) -> bool:
        return False

    async def stream_chat(self, messages: list[ChatMessage], **kwargs):
        """Yield text chunks. Default: single chunk from chat()."""
        yield await self.chat(messages, **kwargs)
