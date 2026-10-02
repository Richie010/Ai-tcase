from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.jobs import create_job, get_job, run_pipeline
from app.models import Job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/jobs", status_code=status.HTTP_201_CREATED)
async def create_generation_job(files: list[UploadFile], background_tasks: BackgroundTasks) -> dict[str, str]:
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No files uploaded")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    saved_paths: list[str] = []
    doc_names: list[str] = []

    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                f"Unsupported file type '{suffix}'. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}",
            )

        contents = await upload.read()
        size_mb = len(contents) / (1024 * 1024)
        if size_mb > settings.MAX_UPLOAD_SIZE_MB:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"{upload.filename} is {size_mb:.1f}MB, exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB limit",
            )

        safe_name = f"{uuid.uuid4().hex}{suffix}"
        dest_path = os.path.join(settings.UPLOAD_DIR, safe_name)
        with open(dest_path, "wb") as f:
            f.write(contents)
        saved_paths.append(dest_path)
        doc_names.append(upload.filename or safe_name)

    job = create_job(doc_names)
    background_tasks.add_task(run_pipeline, job.job_id, saved_paths)
    return {"job_id": job.job_id}


@app.get("/api/jobs/{job_id}", response_model=Job)
async def get_job_status(job_id: str) -> Job:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


@app.get("/api/jobs/{job_id}/download")
async def download_excel(job_id: str) -> FileResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    if job.excel_path is None or not os.path.exists(job.excel_path):
        raise HTTPException(status.HTTP_409_CONFLICT, "Excel file not ready yet")
    return FileResponse(
        job.excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"test_cases_{job_id[:8]}.xlsx",
    )


_frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
