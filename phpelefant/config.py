from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: SecretStr = Field(..., alias="BOT_TOKEN")
    bot_owner_id: int = Field(6104236913, alias="BOT_OWNER_ID")
    official_channel_id: int = Field(-1003908421427, alias="OFFICIAL_CHANNEL_ID")
    database_url: str = Field("sqlite+aiosqlite:///./phpelefant.db", alias="DATABASE_URL")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    enable_eval: bool = Field(False, alias="ENABLE_EVAL")
    delete_service_messages: bool = Field(False, alias="DELETE_SERVICE_MESSAGES")
    default_language: str = Field("en", alias="DEFAULT_LANGUAGE")
    default_timezone: str = Field("UTC", alias="DEFAULT_TIMEZONE")

    @field_validator("bot_owner_id")
    @classmethod
    def validate_owner(cls, value: int) -> int:
        if value != 6104236913:
            raise ValueError("PHPelefant owner ID must remain 6104236913 unless code is audited")
        return value

    @property
    def token(self) -> str:
        return self.bot_token.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()

