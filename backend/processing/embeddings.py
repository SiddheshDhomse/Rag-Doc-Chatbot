from __future__ import annotations

from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
model = SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed_chunks(chunks, batch_size: int = 64):
    if not chunks:
        return []

    return model.encode(
        chunks,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )


def embed_query(query: str):
    if not query.strip():
        raise ValueError("query cannot be empty")

    return model.encode(
        [query],
        batch_size=1,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )[0]
