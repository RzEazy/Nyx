"""Local embedding fallback when provider embed is unavailable."""

_fallback_model = None


def embed_with_fallback(texts: list[str]) -> list[list[float]]:
    global _fallback_model
    if _fallback_model is None:
        from sentence_transformers import SentenceTransformer

        _fallback_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    vectors = _fallback_model.encode(texts, convert_to_numpy=True)
    return [v.tolist() for v in vectors]
