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
    shell_working_directory: str = Field(".", alias="SHELL_WORKING_DIRECTORY")
    shell_timeout_seconds: int = Field(10, alias="SHELL_TIMEOUT_SECONDS")
    shell_output_limit: int = Field(3500, alias="SHELL_OUTPUT_LIMIT")
    shell_extra_allowed_commands: str = Field(
        "fastfetch,neofetch,free,vm_stat,sw_vers",
        alias="SHELL_EXTRA_ALLOWED_COMMANDS",
    )
    root_shell_allowed_commands: str = Field(
        "cat,df,du,fastfetch,free,grep,head,journalctl,ls,ps,rg,ss,stat,tail,uptime,wc",
        alias="ROOT_SHELL_ALLOWED_COMMANDS",
    )
    delete_service_messages: bool = Field(False, alias="DELETE_SERVICE_MESSAGES")
    default_language: str = Field("en", alias="DEFAULT_LANGUAGE")
    default_timezone: str = Field("UTC", alias="DEFAULT_TIMEZONE")

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
        return self.bot_token.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()
