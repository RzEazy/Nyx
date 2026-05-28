from pathlib import Path

import chromadb

from agent.config import Settings, get_settings
from agent.embeddings import embed_with_fallback
from agent.providers.base import LLMProvider

COLLECTION_NAME = "agent_knowledge"


class RAGRetriever:
    def __init__(
        self,
        provider: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._provider = provider
        path = Path(self._settings.chroma_path)
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(path))
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def set_provider(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        if self._provider is not None:
            try:
                return await self._provider.embed(texts)
            except Exception:
                pass
        return embed_with_fallback(texts)

    async def add_documents(self, docs: list[str], ids: list[str]) -> None:
        if len(docs) != len(ids):
            raise ValueError("docs and ids must have the same length")
        embeddings = await self._embed(docs)
        self._collection.upsert(
            documents=docs,
            ids=ids,
            embeddings=embeddings,
        )

    async def query(self, text: str, n: int = 5) -> list[str]:
        query_embeddings = await self._embed([text])
        result = self._collection.query(
            query_embeddings=query_embeddings,
            n_results=n,
        )
        docs = result.get("documents") or [[]]
        return docs[0] if docs else []
