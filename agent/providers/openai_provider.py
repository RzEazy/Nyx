from openai import AsyncOpenAI

from agent.config import Settings
from agent.providers.base import ChatMessage, LLMProvider

EMBED_MODEL = "text-embedding-3-small"


class OpenAIProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(api_key=settings.openai_api_key or None)

    @property
    def model_name(self) -> str:
        return self._settings.openai_model

    @property
    def supports_streaming(self) -> bool:
        return True

    def _to_openai_messages(self, messages: list[ChatMessage]) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in messages]

    async def chat(self, messages: list[ChatMessage], **kwargs) -> str:
        model = kwargs.get("model", self._settings.openai_model)
        response = await self._client.chat.completions.create(
            model=model,
            messages=self._to_openai_messages(messages),
        )
        return response.choices[0].message.content or ""

    async def stream_chat(self, messages: list[ChatMessage], **kwargs):
        model = kwargs.get("model", self._settings.openai_model)
        stream = await self._client.chat.completions.create(
            model=model,
            messages=self._to_openai_messages(messages),
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model=EMBED_MODEL,
            input=texts,
        )
        return [item.embedding for item in response.data]
