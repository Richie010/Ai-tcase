"""
Thin wrapper around the Gemini API (google-generativeai SDK).

Isolated in one module so: (1) it's the only place that needs the API key
and SDK, (2) it's easy to mock in tests, (3) if the SDK or model names
change, only this file needs updating.
"""
from __future__ import annotations

import json
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


class GeminiError(Exception):
    pass


def _client():
    """Lazy import + configure so the rest of the app can be imported/tested
    without the google-generativeai package or an API key being present."""
    import google.generativeai as genai

    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        raise GeminiError("GEMINI_API_KEY is not set. Add it to backend/.env")
    genai.configure(api_key=settings.GEMINI_API_KEY)
    return genai


async def embed_text(text: str) -> list[float]:
    """Embeds a single chunk of text. Called once per chunk at ingest time
    and once per query at retrieval time — not per generation call, which
    is what keeps embedding cost low relative to generation cost."""
    genai = _client()
    settings = get_settings()
    try:
        result = genai.embed_content(
            model=f"models/{settings.GEMINI_EMBEDDING_MODEL}",
            content=text,
            task_type="retrieval_document",
        )
        return result["embedding"]
    except Exception as exc:
        raise GeminiError(f"Embedding request failed: {exc}") from exc


async def embed_query(text: str) -> list[float]:
    genai = _client()
    settings = get_settings()
    try:
        result = genai.embed_content(
            model=f"models/{settings.GEMINI_EMBEDDING_MODEL}",
            content=text,
            task_type="retrieval_query",
        )
        return result["embedding"]
    except Exception as exc:
        raise GeminiError(f"Embedding request failed: {exc}") from exc


async def generate_json(system_instruction: str, user_prompt: str) -> dict:
    """Calls Gemini with a prompt that mandates JSON-only output, and parses
    the result. Raises GeminiError on any failure (network, API, bad JSON)
    so callers only need to catch one exception type."""
    genai = _client()
    settings = get_settings()

    model = genai.GenerativeModel(
        model_name=settings.GEMINI_GENERATION_MODEL,
        system_instruction=system_instruction,
        generation_config={
            "temperature": 0.2,
            "max_output_tokens": settings.GEMINI_MAX_OUTPUT_TOKENS,
            "response_mime_type": "application/json",
        },
    )

    try:
        response = model.generate_content(user_prompt)
    except Exception as exc:
        raise GeminiError(f"Generation request failed: {exc}") from exc

    raw_text = getattr(response, "text", None)
    if not raw_text:
        raise GeminiError("Gemini returned an empty response")

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise GeminiError(f"Gemini returned non-JSON output: {exc}") from exc
