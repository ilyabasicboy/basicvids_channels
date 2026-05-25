from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATA_PATH: Path = Path("./data")
    DATABASE_URL: str = "sqlite:///./data/database.db"
    REDIS_URL: str = "redis://localhost:6379/5"
    AUTH_CURRENT_USER_URL: str = "http://basicvids_auth:8000/api/v1/users/detail/"
    MAX_CHANNEL_AVATAR_SIZE_BYTES: int = 5 * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file="./data/.env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
