from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5"
    rules_path: str = "docs/CATAN-OFFICIAL-RULES.md"

    @property
    def rules_path_resolved(self) -> Path:
        return Path(self.rules_path)


@lru_cache
def get_settings() -> Settings:
    return Settings()
