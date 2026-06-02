from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    log_level: str = Field(default="info", alias="LOG_LEVEL")

    data_dir: Path = Field(default=Path("../data"), alias="DATA_DIR")
    models_dir: Path = Field(default=Path("../models"), alias="MODELS_DIR")
    max_upload_mb: int = Field(default=200, alias="MAX_UPLOAD_MB")

    cors_allow_origins: List[str] = Field(default_factory=lambda: ["*"], alias="CORS_ALLOW_ORIGINS")

    def resolved_data_dir(self) -> Path:
        p = Path(self.data_dir)
        if not p.is_absolute():
            p = (_BACKEND_DIR / p).resolve()
        return p

    def resolved_models_dir(self) -> Path:
        p = Path(self.models_dir)
        if not p.is_absolute():
            p = (_BACKEND_DIR / p).resolve()
        return p


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
