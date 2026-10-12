from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", BACKEND_DIR / ".env.local"),
        extra="ignore",
    )

    database_url: SecretStr = Field(default=SecretStr(""), validation_alias="DATABASE_URL")
    environment: Literal["local", "staging", "production"] = "local"
    requests_per_minute: int = 120
    omdb_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="OMDB_API_KEY")


settings = Settings()
