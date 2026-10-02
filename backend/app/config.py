"""Centralized settings, loaded from environment / .env. Import get_settings()
everywhere else — never read os.environ directly in other modules."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "AI Test Case Portal"
    DEBUG: bool = False

    # --- Gemini ---
    GEMINI_API_KEY: str = "AQ.Ab8RN6K7iTVSOfuIrJjli6QZoIfFrZHVxHZ4JYWgmaHsbuPizw"  
    GEMINI_GENERATION_MODEL: str = "gemini-3.8-flash"       # cheap/fast — good default for structured generation
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    GEMINI_MAX_OUTPUT_TOKENS: int = 8192

    # --- RAG / chunking (tuned to keep per-call token usage low) ---
    CHUNK_SIZE_CHARS: int = 1800          # ~450 tokens/chunk, keeps embedding+retrieval cheap
    CHUNK_OVERLAP_CHARS: int = 200
    RETRIEVAL_TOP_K: int = 6              # only the most relevant chunks go into each generation prompt
    MAX_SECTIONS_PER_GENERATION_CALL: int = 1  # generate per-section instead of one giant prompt

    # --- Uploads ---
    MAX_UPLOAD_SIZE_MB: int = 20
    ALLOWED_EXTENSIONS: tuple[str, ...] = (".pdf", ".docx", ".xlsx", ".xls")
    UPLOAD_DIR: str = "./data/uploads"
    EXPORT_DIR: str = "./data/exports"


@lru_cache
def get_settings() -> Settings:
    return Settings()
