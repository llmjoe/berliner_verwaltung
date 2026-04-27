from __future__ import annotations

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://bv:bv@localhost:5432/berliner_verwaltung"
    )

    oparl_base_url: str = (
        "https://www.berlin.de/ba-friedrichshain-kreuzberg"
        "/politik-und-verwaltung/bezirksverordnetenversammlung"
        "/online/oparl/v1.1"
    )

    anthropic_api_key: str = ""
    openai_api_key: str = ""

    ollama_base_url: str = "http://localhost:11434"

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"


settings = Settings()
