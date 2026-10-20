from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env — resolved relative to this file so it is found regardless of CWD.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Application settings, loaded from the environment / backend/.env."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    test_database_url: str = ""
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    # 30 days: the owner should not meet the login screen again after signing up
    # once (FEATURES.md F1 manual check). No refresh token in the MVP.
    jwt_expires_minutes: int = 60 * 24 * 30
    tz: str = "Asia/Kolkata"


@lru_cache
def get_settings() -> Settings:
    return Settings()
