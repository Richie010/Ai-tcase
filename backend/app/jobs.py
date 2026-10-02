"""
In-memory job tracking + the orchestration pipeline.

No Redis/Celery here deliberately — this app processes one upload at a
time per user session, so an in-process dict plus FastAPI BackgroundTasks
is enough and keeps the whole thing a single deployable process. If this
needs to scale to many concurrent heavy jobs later, swap this module for a
real queue without touching extraction/chunking/generation/export.
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from app.chunking import chunk_sections
from app.config import get_settings
from app.excel_export import export_to_file
from app.extraction import ExtractionError, extract_document
from app.gemini_client import GeminiError, embed_text
from app.models import Job, JobStatus
from app.testcase_generator import generate_test_cases_for_document
from app.vector_store import InMemoryVectorStore

logger = logging.getLogger(__name__)

_JOBS: dict[str, Job] = {}


def create_job(document_names: list[str]) -> Job:
    job = Job(job_id=str(uuid.uuid4()), document_names=document_names)
    _JOBS[job.job_id] = job
    return job


def get_job(job_id: str) -> Job | None:
    return _JOBS.get(job_id)


def _update(job: Job, **kwargs) -> None:
    for key, value in kwargs.items():
        setattr(job, key, value)


async def run_pipeline(job_id: str, file_paths: list[str]) -> None:
    job = _JOBS[job_id]
    settings = get_settings()

    try:
        # --- Extraction ---
        _update(job, status=JobStatus.EXTRACTING, current_stage="Extracting text from documents", progress_percent=10)
        all_chunks = []
        for path in file_paths:
            doc_name = Path(path).name
            try:
                sections = extract_document(path)
            except ExtractionError as exc:
                raise RuntimeError(f"Extraction failed for {doc_name}: {exc}") from exc
            all_chunks.extend(chunk_sections(doc_name, sections))

        if not all_chunks:
            raise RuntimeError("No content could be extracted from the uploaded document(s)")

        # --- Embedding ---
        _update(job, status=JobStatus.EMBEDDING, current_stage=f"Embedding {len(all_chunks)} chunks", progress_percent=30)
        store = InMemoryVectorStore()
        embedded = []
        for chunk in all_chunks:
            try:
                chunk.embedding = await embed_text(chunk.text)
                embedded.append(chunk)
            except GeminiError as exc:
                logger.warning("embedding_failed_for_chunk", extra={"chunk_id": chunk.chunk_id, "error": str(exc)})
        if not embedded:
            raise RuntimeError("Embedding failed for all document chunks — check GEMINI_API_KEY")

        # --- Generation (RAG) ---
        _update(job, status=JobStatus.GENERATING, current_stage="Generating test cases", progress_percent=60)
        test_cases = await generate_test_cases_for_document(embedded, store, top_k=settings.RETRIEVAL_TOP_K)
        if not test_cases:
            raise RuntimeError("No test cases could be generated from the document content")

        # --- Export ---
        _update(job, current_stage="Building Excel workbook", progress_percent=90)
        os.makedirs(settings.EXPORT_DIR, exist_ok=True)
        excel_path = os.path.join(settings.EXPORT_DIR, f"{job_id}_test_cases.xlsx")
        export_to_file(test_cases, excel_path)

        _update(
            job,
            status=JobStatus.COMPLETED,
            current_stage="Done",
            progress_percent=100,
            test_cases=test_cases,
            excel_path=excel_path,
        )

    except Exception as exc:  # noqa: BLE001 — job pipeline boundary, must not crash the worker
        logger.exception("job_pipeline_failed", extra={"job_id": job_id})
        _update(job, status=JobStatus.FAILED, error_message=str(exc))
