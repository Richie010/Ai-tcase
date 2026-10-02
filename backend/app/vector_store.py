"""
Minimal in-memory vector store.

For a single-session "upload a document, get test cases" workflow, a full
vector database (Qdrant/Pinecone/etc.) is unnecessary overhead — a
document's chunks (typically tens to low hundreds) fit comfortably in
memory, and cosine similarity over a numpy matrix is fast enough. If this
app later needs to persist embeddings across sessions or scale to many
concurrent large documents, swap this module for a real vector DB without
touching the RAG or generation logic, since both only depend on
`InMemoryVectorStore.search()`.
"""
from __future__ import annotations

import numpy as np

from app.models import DocumentChunk


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._chunks: list[DocumentChunk] = []
        self._matrix: np.ndarray | None = None

    def add(self, chunks: list[DocumentChunk]) -> None:
        for chunk in chunks:
            if chunk.embedding is None:
                raise ValueError(f"Chunk {chunk.chunk_id} has no embedding — embed before adding to the store")
        self._chunks.extend(chunks)
        vectors = np.array([c.embedding for c in self._chunks], dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1e-10
        self._matrix = vectors / norms

    def search(self, query_embedding: list[float], top_k: int) -> list[DocumentChunk]:
        if self._matrix is None or len(self._chunks) == 0:
            return []
        query = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return []
        query = query / query_norm
        scores = self._matrix @ query
        top_k = min(top_k, len(self._chunks))
        top_indices = np.argsort(-scores)[:top_k]
        return [self._chunks[i] for i in top_indices]

    def all_chunks(self) -> list[DocumentChunk]:
        return list(self._chunks)

    def __len__(self) -> int:
        return len(self._chunks)
