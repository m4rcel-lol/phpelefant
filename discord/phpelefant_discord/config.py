from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    discord_token: SecretStr = Field(..., alias="DISCORD_TOKEN")
    bot_owner_id: int = Field(6104236913, alias="BOT_OWNER_ID")
    official_channel_id: int = Field(0, alias="OFFICIAL_CHANNEL_ID")
    command_prefix: str = Field("!", alias="COMMAND_PREFIX")
    database_url: str = Field("sqlite+aiosqlite:///./phpelefant-discord.db", alias="DATABASE_URL")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    enable_eval: bool = Field(False, alias="ENABLE_EVAL")
    shell_working_directory: str = Field(".", alias="SHELL_WORKING_DIRECTORY")
    shell_path: str = Field("/bin/sh", alias="SHELL_PATH")
    shell_runtime_user: str = Field("phpelefant-env", alias="SHELL_RUNTIME_USER")
    shell_enforce_runtime_user: bool = Field(True, alias="SHELL_ENFORCE_RUNTIME_USER")
    shell_timeout_seconds: int = Field(10, alias="SHELL_TIMEOUT_SECONDS")
    shell_output_limit: int = Field(3500, alias="SHELL_OUTPUT_LIMIT")
    default_language: str = Field("en", alias="DEFAULT_LANGUAGE")
    default_timezone: str = Field("UTC", alias="DEFAULT_TIMEZONE")
    xp_cooldown_seconds: int = Field(45, alias="XP_COOLDOWN_SECONDS")

    @field_validator("bot_owner_id")
    @classmethod
    def validate_owner(cls, value: int) -> int:
        if value != 6104236913:
            raise ValueError("PHPelefant owner ID must remain 6104236913 unless code is audited")
        return value

    @field_validator("shell_timeout_seconds")
    @classmethod
    def validate_shell_timeout(cls, value: int) -> int:
        if not 1 <= value <= 30:
            raise ValueError("SHELL_TIMEOUT_SECONDS must be between 1 and 30")
        return value

    @field_validator("shell_output_limit")
    @classmethod
    def validate_shell_output_limit(cls, value: int) -> int:
        if not 500 <= value <= 3900:
            raise ValueError("SHELL_OUTPUT_LIMIT must be between 500 and 3900")
        return value

    @property
    def token(self) -> str:
        return self.discord_token.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()

