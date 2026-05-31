from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "会唱歌的数字人"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    MODELS_DIR: Path = BASE_DIR / "models"
    UPLOAD_DIR: Path = DATA_DIR / "uploads"
    AVATAR_DIR: Path = DATA_DIR / "avatars"
    OUTPUT_DIR: Path = DATA_DIR / "output"

    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    model_config = {"env_prefix": "SDH_", "env_file": ".env"}


settings = Settings()
