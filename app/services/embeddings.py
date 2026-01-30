"""HuggingFace sentence-transformers embeddings service (singleton)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import EMBEDDING_MODEL

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


_model: "SentenceTransformer | None" = None


def _get_model() -> "SentenceTransformer":
    """Load model once at startup (singleton)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts. Returns list of embedding vectors."""
    if not texts:
        return []
    model = _get_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return [e.tolist() for e in embeddings]


def embed_query(query: str) -> list[float]:
    """Embed a single query string."""
    model = _get_model()
    emb = model.encode(query, convert_to_numpy=True)
    return emb.tolist()


def warmup() -> None:
    """Load model (e.g. for @st.cache_resource warmup)."""
    _get_model()
