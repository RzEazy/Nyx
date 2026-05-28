from anthropic import AsyncAnthropic

from agent.config import Settings
from agent.providers.base import ChatMessage, LLMProvider
from agent.embeddings import embed_with_fallback


class AnthropicProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key or None)

    @property
    def model_name(self) -> str:
        return self._settings.anthropic_model

    @property
    def supports_streaming(self) -> bool:
        return True

    def _split_system(self, messages: list[ChatMessage]) -> tuple[str | None, list[dict]]:
        system_parts: list[str] = []
        conv: list[dict] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
            else:
                conv.append({"role": m.role, "content": m.content})
        system = "\n\n".join(system_parts) if system_parts else None
        return system, conv

    async def chat(self, messages: list[ChatMessage], **kwargs) -> str:
        model = kwargs.get("model", self._settings.anthropic_model)
        system, conv = self._split_system(messages)
        kwargs_create: dict = {
            "model": model,
            "max_tokens": 4096,
            "messages": conv,
        }
        if system:
            kwargs_create["system"] = system
        response = await self._client.messages.create(**kwargs_create)
        parts = [b.text for b in response.content if b.type == "text"]
        return "".join(parts)

    async def stream_chat(self, messages: list[ChatMessage], **kwargs):
        model = kwargs.get("model", self._settings.anthropic_model)
        system, conv = self._split_system(messages)
        kwargs_create: dict = {
            "model": model,
            "max_tokens": 4096,
            "messages": conv,
        }
        if system:
            kwargs_create["system"] = system
        async with self._client.messages.stream(**kwargs_create) as stream:
            async for text in stream.text_stream:
                yield text

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return embed_with_fallback(texts)
