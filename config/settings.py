"""Central configuration. Secrets come from environment variables only."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    llm_api_key: str
    llm_model: str
    newsapi_key: str
    request_timeout: int
    max_retries: int
    cache_ttl: int
    sample_data_path: Path

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)


def get_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    return Settings(
        llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_model=os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash").strip(),
        newsapi_key=os.getenv("NEWSAPI_KEY", "").strip(),
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "15")),
        max_retries=max(1, int(os.getenv("MAX_RETRIES", "3"))),
        cache_ttl=int(os.getenv("CACHE_TTL_SECONDS", "900")),
        sample_data_path=ROOT / "data" / "sample_stock_data.csv",
    )
