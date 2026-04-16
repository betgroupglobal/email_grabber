"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LEAD_PIPELINE_", case_sensitive=False)

    secret_key: str = Field(default="dev-only-do-not-use-in-prod", min_length=16)
    base_url: str = "http://localhost:8000"
    from_email: str = "noreply@example.com"
    from_name: str = "BetGroup Research"
    confirm_token_max_age_seconds: int = 60 * 60 * 24 * 7  # 7 days
    unconfirmed_purge_seconds: int = 60 * 60 * 24 * 7

    database_url: str = Field(
        default="sqlite+pysqlite:///./lead_pipeline.db",
        validation_alias="DATABASE_URL",
    )

    resend_api_key: str = Field(default="", validation_alias="RESEND_API_KEY")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
