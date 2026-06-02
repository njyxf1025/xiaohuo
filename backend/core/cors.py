from __future__ import annotations

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

from .config import get_settings


def install_cors(app: FastAPI) -> None:
    settings = get_settings()
    origins = settings.cors_allow_origins or ["*"]
    allow_origins = origins
    allow_credentials = True
    if origins == ["*"]:
        allow_credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
