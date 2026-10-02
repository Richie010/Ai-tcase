"""Splits extracted document sections into bounded chunks for embedding.

Chunking (rather than embedding whole pages/sheets) is what makes the RAG
step token-efficient: retrieval later pulls only the few most relevant
chunks into the generation prompt instead of the entire document.
"""
from __future__ import annotations

import uuid

from app.config import get_settings
from app.extraction import ExtractedSection
from app.models import DocumentChunk


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # try to break on a paragraph/sentence boundary near the end
        if end < len(text):
            boundary = text.rfind("\n", start, end)
            if boundary == -1 or boundary <= start + chunk_size // 2:
                boundary = text.rfind(". ", start, end)
            if boundary != -1 and boundary > start:
                end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = max(end - overlap, start + 1)
    return chunks


def chunk_sections(document_name: str, sections: list[ExtractedSection]) -> list[DocumentChunk]:
    settings = get_settings()
    chunks: list[DocumentChunk] = []

    for section in sections:
        pieces = _split_text(section.text, settings.CHUNK_SIZE_CHARS, settings.CHUNK_OVERLAP_CHARS)
        for piece in pieces:
            chunks.append(
                DocumentChunk(
                    chunk_id=str(uuid.uuid4()),
                    document_name=document_name,
                    section_title=section.section_title,
                    text=piece,
                    page_or_sheet=section.location,
                )
            )
    return chunks
