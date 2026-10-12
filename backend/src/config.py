from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WATCHSIFT_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    environment: Literal["local", "staging", "production"] = "local"
    requests_per_minute: int = 120


settings = Settings()
