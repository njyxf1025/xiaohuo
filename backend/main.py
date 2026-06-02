from __future__ import annotations

import sys
import traceback
import uuid
from contextvars import ContextVar
from typing import Any

if "core.request_id" not in sys.modules:
    _stub_request_id = type(sys)("core.request_id")
    _stub_request_id.__file__ = __file__
    _stub_request_id.__package__ = "core"
    _stub_request_id.__path__ = []
    _stub_request_id.request_id_ctx = ContextVar("request_id", default="-")

    def _get_request_id() -> str:
        try:
            return _stub_request_id.request_id_ctx.get()
        except LookupError:
            return "-"

    def _set_request_id(value: str) -> None:
        _stub_request_id.request_id_ctx.set(value)

    def _new_request_id() -> str:
        return uuid.uuid4().hex

    from starlette.middleware.base import BaseHTTPMiddleware

    class _RequestIDMiddleware(BaseHTTPMiddleware):
        HEADER = "X-Request-ID"

        def __init__(self, app, header: str = HEADER):
            super().__init__(app)
            self.header = header
            import logging as _lg

            self._logger = _lg.getLogger("core.request_id")

        async def dispatch(self, request, call_next):
            import time

            incoming = request.headers.get(self.header)
            rid = incoming if incoming else _new_request_id()
            token = _stub_request_id.request_id_ctx.set(rid)
            start = time.perf_counter()
            try:
                response = await call_next(request)
            except Exception:
                duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
                self._logger.exception(
                    "request failed",
                    extra={"stage": "request", "duration_ms": duration_ms},
                )
                raise
            finally:
                _stub_request_id.request_id_ctx.reset(token)
            duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
            response.headers[self.header] = rid
            self._logger.info(
                "request handled",
                extra={
                    "stage": "request",
                    "duration_ms": duration_ms,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                },
            )
            return response

    _stub_request_id.get_request_id = _get_request_id
    _stub_request_id.set_request_id = _set_request_id
    _stub_request_id.new_request_id = _new_request_id
    _stub_request_id.RequestIDMiddleware = _RequestIDMiddleware
    sys.modules["core.request_id"] = _stub_request_id

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from api import avatar, generation, music
from api.system import router as system_router
from core import gpu, onnx_provider
from core.config import get_settings
from core.cors import install_cors
from core.logging import configure_logging, get_logger
from core.request_id import RequestIDMiddleware, get_request_id

_logger = get_logger("core.main")


def _register_or_include(app: FastAPI, module, attr_name: str, router_name: str) -> None:
    register_fn = getattr(module, attr_name, None)
    if callable(register_fn):
        register_fn(app)
        return
    router = getattr(module, router_name, None)
    if router is not None:
        app.include_router(router, prefix="/api/v1")
        return
    _logger.warning(
        "router module %s exposes neither %s nor '%s' attribute",
        module.__name__,
        attr_name,
        router_name,
    )


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Singing Digital Human Backend",
        version="0.1.0",
        description="FastAPI backend powering the Singing Digital Human web app.",
    )

    install_cors(app)
    app.add_middleware(RequestIDMiddleware)

    api_v1 = APIRouter()
    api_v1.include_router(system_router, tags=["system"])
    app.include_router(api_v1, prefix="/api/v1")

    _register_or_include(app, music, "register_music_routes", "router")
    _register_or_include(app, avatar, "register_avatar_routes", "router")
    _register_or_include(app, generation, "register_generation_routes", "router")

    @app.exception_handler(Exception)
    async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        rid = get_request_id()
        _logger.error(
            "unhandled exception: %s",
            exc,
            extra={
                "stage": "unhandled",
                "error": type(exc).__name__,
                "err_message": str(exc),
                "path": str(request.url.path),
                "method": request.method,
                "request_id": rid,
            },
        )
        _logger.debug("traceback:\n%s", traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": str(exc) or "an unexpected error occurred",
                "request_id": rid,
            },
        )

    @app.on_event("startup")
    async def _startup() -> None:
        settings = get_settings()
        _logger.info(
            "startup",
            extra={
                "stage": "startup",
                "api_host": settings.api_host,
                "api_port": settings.api_port,
                "log_level": settings.log_level,
            },
        )
        try:
            data_dir = settings.resolved_data_dir()
            data_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            _logger.warning("failed to prepare DATA_DIR: %s", exc)
        try:
            models_dir = settings.resolved_models_dir()
            models_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            _logger.warning("failed to prepare MODELS_DIR: %s", exc)

        try:
            gpus = gpu.detect_gpus()
            _logger.info(
                "GPU summary",
                extra={
                    "stage": "startup.gpu",
                    "count": len(gpus),
                    "devices": gpus,
                },
            )
        except Exception as exc:
            _logger.exception("GPU detection failed: %s", exc)

        try:
            dml_ok, dml_reason = onnx_provider.is_directml_available()
            if dml_ok:
                providers, label = onnx_provider.select_providers()
                _logger.info(
                    "ONNX provider selected (DirectML required, CPU fallback disabled)",
                    extra={
                        "stage": "startup.onnx",
                        "chosen": label,
                        "providers": providers,
                    },
                )
            else:
                _logger.critical(
                    "FATAL: DirectML not available. CPU fallback has been disabled. "
                    "Reason: %s. "
                    "Install onnxruntime-directml and ensure a DirectML-capable GPU is present. "
                    "The /api/v1/health endpoint will return HTTP 503 until this is resolved.",
                    dml_reason,
                    extra={
                        "stage": "startup.onnx",
                        "error_code": "directml_unavailable",
                        "reason": dml_reason,
                    },
                )
        except Exception as exc:
            _logger.critical(
                "FATAL: ONNX provider probe failed: %s. CPU fallback disabled.",
                exc,
                exc_info=True,
                extra={
                    "stage": "startup.onnx",
                    "error_code": "onnx_probe_failed",
                },
            )

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        _logger.info("shutdown", extra={"stage": "shutdown"})

    @app.get("/")
    async def root() -> dict[str, Any]:
        return {
            "name": "Singing Digital Human Backend",
            "version": "0.1.0",
            "api_prefix": "/api/v1",
        }

    return app


app = create_app()
