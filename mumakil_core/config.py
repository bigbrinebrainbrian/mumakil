"""Configuration Manager for Mumakil 2.0.

Provides centralized configuration loading using Pydantic Settings,
supporting .env files and fallback reading from legacy config/ files.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_file_stripped(path: Path) -> Optional[str]:
    """Helper to read text from file if it exists, stripped of whitespace."""
    if path.is_file():
        try:
            content = path.read_text(encoding="utf-8").strip()
            return content if content else None
        except Exception:
            return None
    return None


class Settings(BaseSettings):
    """Application settings with environment variable and file fallback support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Base workspace directory
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent)

    # API Keys & Auth Tokens
    gemini_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-2.0-flash")
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/models"
    )
    qc_token: str = Field(default="a1b2c3d4-e5f6-7890-abcd-ef1234567890")

    # Target Backend Configuration
    target_base_url: str = Field(
        default="http://localhost/project_dbmigas/index.php"
    )
    legacy_analyze_url: str = Field(
        default="http://localhost/automation_dbmigas/analyze.php"
    )

    # Server Configuration
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    debug: bool = Field(default=False)

    # Storage & Persistence
    storage_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "storage"
    )
    log_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "storage" / "logs"
    )
    sqlite_db_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "storage" / "mumakil_state.db"
    )

    # Async Engine Limits & Performance
    request_timeout_seconds: float = Field(default=15.0)
    ai_timeout_seconds: float = Field(default=20.0)
    max_retries: int = Field(default=3)
    concurrency_limit: int = Field(default=20)
    connection_pool_limits_max: int = Field(default=100)
    connection_pool_limits_keepalive: int = Field(default=50)

    def model_post_init(self, __context) -> None:
        """Fallback to legacy config files if environment variables are not set."""
        # 1. Fallback for Gemini API key
        if not self.gemini_api_key:
            legacy_key_path = self.base_dir / "config" / "api_key.txt"
            val = _read_file_stripped(legacy_key_path)
            if val:
                object.__setattr__(self, "gemini_api_key", val)

        # 2. Fallback for QC Token
        if not self.qc_token or self.qc_token == "a1b2c3d4-e5f6-7890-abcd-ef1234567890":
            legacy_token_path = self.base_dir / "config" / "qc_token.txt"
            val = _read_file_stripped(legacy_token_path)
            if val:
                object.__setattr__(self, "qc_token", val)

        # 3. Ensure directories exist
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
