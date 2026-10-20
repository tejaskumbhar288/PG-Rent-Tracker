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

    # Browser origins allowed to call the API. Only the Expo web dev server by
    # default. The phone does not need this — React Native's fetch does not
    # enforce origins — but a browser blocks every response without it.
    cors_origins: str = (
        "http://localhost:8081,http://127.0.0.1:8081,http://localhost:19006,http://127.0.0.1:19006"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """``cors_origins`` split into a list, ignoring blanks."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
