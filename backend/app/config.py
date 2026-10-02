"""Centralized settings, loaded from environment / .env. Import get_settings()
everywhere else — never read os.environ directly in other modules."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str
    DEBUG: bool

    # --- Gemini ---
    GEMINI_API_KEY: str
    GEMINI_GENERATION_MODEL: str
    GEMINI_EMBEDDING_MODEL: str
    GEMINI_MAX_OUTPUT_TOKENS: int

    # --- RAG / chunking ---
    CHUNK_SIZE_CHARS: int
    CHUNK_OVERLAP_CHARS: int
    RETRIEVAL_TOP_K: int
    MAX_SECTIONS_PER_GENERATION_CALL: int

    # --- Uploads ---
    MAX_UPLOAD_SIZE_MB: int
    ALLOWED_EXTENSIONS: str
    UPLOAD_DIR: str
    EXPORT_DIR: str

    @property
    def allowed_extensions_list(self) -> tuple[str, ...]:
        return tuple(ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(","))


@lru_cache
def get_settings() -> Settings:
    return Settings()