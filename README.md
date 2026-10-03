# AI Test Case Portal

Upload requirement documents (PDF, DOCX, or Excel) and instantly get a formatted Excel workbook of generated test cases — positive, negative, boundary, and edge — powered by RAG with Gemini.

> Single FastAPI backend serves both the API and the frontend. One process, one port, zero build steps.

---

## How It Works

```
Upload (PDF / DOCX / XLSX)
        │
        ▼
   Extraction ─── PyMuPDF · python-docx · openpyxl → structured text
        │
        ▼
    Chunking ──── ~450-token chunks for efficient embedding
        │
        ▼
   Embedding ──── Gemini text-embedding-004
        │
        ▼
  Vector Store ── in-memory cosine similarity (NumPy)
        │
        ▼
 RAG Generation ─ top-K retrieval per module → Gemini Flash → JSON output
        │
        ▼
  Excel Export ── formatted & color-coded workbook (Summary + Test Cases)
```

---

## Project Layout

```
backend/
  app/
    main.py                  # FastAPI app, routes, serves frontend
    config.py                # env-driven settings
    models.py                # Pydantic schemas
    extraction.py            # PDF/DOCX/XLSX → structured text
    chunking.py              # text → bounded chunks
    gemini_client.py         # Gemini API (embedding + generation)
    vector_store.py          # in-memory cosine-similarity search
    testcase_generator.py    # RAG orchestration + prompt
    excel_export.py          # OpenPyXL workbook builder
    jobs.py                  # job store + pipeline orchestration
  requirements.txt
  .env.example
frontend/
  index.html
  app.js
  styles.css
tests/
  test_pipeline_integration.py
sample_data/
  login_module.pdf
  checkout_module.docx
  user_fields.xlsx
```

---

## Quick Start

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Set your GEMINI_API_KEY → https://aistudio.google.com/apikey

uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000** — upload a file from `sample_data/` to try it out.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/health` | Health check |
| `POST` | `/api/jobs` | Upload files, starts generation job → `{ job_id }` |
| `GET`  | `/api/jobs/{job_id}` | Poll job status & progress |
| `GET`  | `/api/jobs/{job_id}/download` | Download generated Excel workbook |

---

## Run Tests

```bash
pytest tests/ -v
```

Tests mock all Gemini API calls — no API key or network needed. Exercises the full pipeline: upload, extraction, chunking, vector store, job lifecycle, and Excel output.

---

## Design Decisions

- **Chunked prompts, not whole-document** — the LLM sees only relevant chunks per module, keeping token usage low.
- **Retrieval over concatenation** — related context is pulled by embedding similarity, not brute-force inclusion.
- **One generation call per module** — fewer round trips, batch test-case output.
- **JSON-only output** with capped `max_output_tokens` — no wasted tokens on prose.
- **In-memory job storage** — lightweight for single-user use; swap for Redis/DB for persistence.

---

## License

MIT
![alt text](image.png)



![alt text](image-1.png)



![alt text](image-3.png)



