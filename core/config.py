from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="RSC_", extra="ignore")

    owner_api_key: str = "change-me"
    database_url: str = "sqlite:///./data/app.db"
    public_base_url: str = "http://127.0.0.1:8000"
    server_url: str = "http://127.0.0.1:8000"
    media_dir: str = "data/media"
    media_ttl_seconds: int = 600
    pairing_ttl_seconds: int = 600
    telegram_token: str = ""
    telegram_owner_ids: str = ""

    @property
    def owner_telegram_ids(self) -> set[int]:
        result: set[int] = set()
        for raw in self.telegram_owner_ids.split(","):
            raw = raw.strip()
            if raw:
                result.add(int(raw))
        return result


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
