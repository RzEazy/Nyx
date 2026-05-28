import cohere

from agent.config import Settings
from agent.providers.base import ChatMessage, LLMProvider

EMBED_MODEL = "embed-english-v3.0"


class CohereProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = cohere.AsyncClientV2(api_key=settings.cohere_api_key or None)

    @property
    def model_name(self) -> str:
        return self._settings.cohere_model

    @property
    def supports_streaming(self) -> bool:
        return True

    def _to_cohere_messages(self, messages: list[ChatMessage]) -> list[dict]:
        system_parts: list[str] = []
        out: list[dict] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
                continue
            role = "assistant" if m.role == "assistant" else "user"
            out.append({"role": role, "content": m.content})
        if system_parts:
            merged = "\n\n".join(system_parts)
            out.insert(0, {"role": "system", "content": merged})
        return out

    async def chat(self, messages: list[ChatMessage], **kwargs) -> str:
        model = kwargs.get("model", self._settings.cohere_model)
        response = await self._client.chat(
            model=model,
            messages=self._to_cohere_messages(messages),
        )
        return response.message.content[0].text

    async def stream_chat(self, messages: list[ChatMessage], **kwargs):
        model = kwargs.get("model", self._settings.cohere_model)
        stream = await self._client.chat_stream(
            model=model,
            messages=self._to_cohere_messages(messages),
        )
        async for event in stream:
            if event.type == "content-delta":
                yield event.delta.message.content.text

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embed(
            texts=texts,
            model=EMBED_MODEL,
            input_type="search_document",
        )
        return [list(v) for v in response.embeddings.float_]
