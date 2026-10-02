"""
End-to-end pipeline test with Gemini calls mocked.

This sandbox has no network access to the Gemini API, so embed_text /
embed_query / generate_json are monkeypatched with deterministic fakes.
Everything else — file upload, extraction, chunking, the in-memory vector
store, job state transitions, and the Excel export — runs for real.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

os.environ.setdefault("GEMINI_API_KEY", "test-key-not-used")

from app import gemini_client  # noqa: E402
from app.main import app  # noqa: E402

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "sample_data"


async def _fake_embed(text: str) -> list[float]:
    # Deterministic fake embedding: hash-based, stable for the same text,
    # distinct enough to exercise the cosine-similarity search path.
    import hashlib

    h = hashlib.sha256(text.encode()).digest()
    return [b / 255.0 for b in h[:16]]


async def _fake_generate_json(system_instruction: str, user_prompt: str) -> dict:
    return {
        "test_cases": [
            {
                "scenario": "Generated scenario for module",
                "preconditions": "Preconditions text",
                "steps": ["Step one", "Step two"],
                "test_data": "sample=data",
                "expected_result": "Expected outcome text",
                "priority": "P1",
                "case_type": "positive",
            },
            {
                "scenario": "Negative path scenario",
                "preconditions": "Preconditions text",
                "steps": ["Step one"],
                "test_data": "invalid=data",
                "expected_result": "Error shown",
                "priority": "P2",
                "case_type": "negative",
            },
        ]
    }


@pytest.fixture(autouse=True)
def mock_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gemini_client, "embed_text", _fake_embed)
    monkeypatch.setattr(gemini_client, "embed_query", _fake_embed)
    monkeypatch.setattr(gemini_client, "generate_json", _fake_generate_json)
    # app.jobs imported these names directly, so patch them there too
    import app.jobs as jobs_module

    monkeypatch.setattr(jobs_module, "embed_text", _fake_embed)
    import app.testcase_generator as gen_module

    monkeypatch.setattr(gen_module, "embed_query", _fake_embed)
    monkeypatch.setattr(gen_module, "generate_json", _fake_generate_json)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_reject_unsupported_file_type(client: TestClient) -> None:
    resp = client.post(
        "/api/jobs",
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
    )
    assert resp.status_code == 415


def test_full_pipeline_pdf_to_excel(client: TestClient) -> None:
    pdf_path = SAMPLE_DIR / "login_module.pdf"
    assert pdf_path.exists(), "sample PDF must exist — run sample generation first"

    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/api/jobs",
            files=[("files", ("login_module.pdf", f.read(), "application/pdf"))],
        )
    assert resp.status_code == 201
    job_id = resp.json()["job_id"]

    # Poll for completion (background task runs async relative to the request)
    deadline = time.time() + 15
    status_body = None
    while time.time() < deadline:
        status_resp = client.get(f"/api/jobs/{job_id}")
        assert status_resp.status_code == 200
        status_body = status_resp.json()
        if status_body["status"] in ("completed", "failed"):
            break
        time.sleep(0.2)

    assert status_body is not None
    assert status_body["status"] == "completed", status_body.get("error_message")
    assert len(status_body["test_cases"]) >= 1
    assert status_body["test_cases"][0]["tc_id"] == "TC-0001"

    download_resp = client.get(f"/api/jobs/{job_id}/download")
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert len(download_resp.content) > 0


def test_full_pipeline_multi_file_docx_and_xlsx(client: TestClient) -> None:
    docx_path = SAMPLE_DIR / "checkout_module.docx"
    xlsx_path = SAMPLE_DIR / "user_fields.xlsx"

    with open(docx_path, "rb") as f1, open(xlsx_path, "rb") as f2:
        resp = client.post(
            "/api/jobs",
            files=[
                ("files", ("checkout_module.docx", f1.read(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
                ("files", ("user_fields.xlsx", f2.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
            ],
        )
    assert resp.status_code == 201
    job_id = resp.json()["job_id"]

    deadline = time.time() + 15
    status_body = None
    while time.time() < deadline:
        status_body = client.get(f"/api/jobs/{job_id}").json()
        if status_body["status"] in ("completed", "failed"):
            break
        time.sleep(0.2)

    assert status_body["status"] == "completed", status_body.get("error_message")
    modules = {tc["module"] for tc in status_body["test_cases"]}
    assert len(modules) >= 2  # both documents contributed modules


def test_job_not_found_returns_404(client: TestClient) -> None:
    resp = client.get("/api/jobs/nonexistent-job-id")
    assert resp.status_code == 404
