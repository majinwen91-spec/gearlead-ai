from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional convenience dependency
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _as_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    project_root: Path
    database_path: Path
    demo_mode: bool
    openai_api_key: str
    openai_model: str
    openai_base_url: str

    @property
    def llm_available(self) -> bool:
        return bool(self.openai_api_key) and not self.demo_mode


def get_settings() -> Settings:
    if load_dotenv:
        load_dotenv(PROJECT_ROOT / ".env")
    raw_db_path = Path(os.getenv("DATABASE_PATH", "gearlead.db"))
    if not raw_db_path.is_absolute():
        raw_db_path = PROJECT_ROOT / raw_db_path
    return Settings(
        project_root=PROJECT_ROOT,
        database_path=raw_db_path,
        demo_mode=_as_bool(os.getenv("DEMO_MODE"), default=True),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
    )

