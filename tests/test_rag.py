import pytest

from agent.embeddings import embed_with_fallback
from agent.rag.retriever import RAGRetriever


@pytest.mark.asyncio
async def test_add_and_query(tmp_path) -> None:
    from agent.config import Settings

    settings = Settings(chroma_path=str(tmp_path / "chroma"))
    rag = RAGRetriever(settings=settings)
    await rag.add_documents(
        ["Python is a programming language.", "Textual is a TUI framework."],
        ["doc1", "doc2"],
    )
    results = await rag.query("terminal UI library", n=1)
    assert len(results) >= 1
    assert isinstance(results[0], str)


def test_embed_fallback() -> None:
    vecs = embed_with_fallback(["hello", "world"])
    assert len(vecs) == 2
    assert len(vecs[0]) > 0
