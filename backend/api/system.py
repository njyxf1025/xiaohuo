from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from core import gpu, onnx_provider
from core.config import get_settings
from core.request_id import get_request_id
from core.onnx_provider import DirectMLNotAvailable

router = APIRouter()


def _build_payload(rid: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        gpus = gpu.detect_gpus()
    except Exception:
        gpus = []
    dml_ok, dml_reason = onnx_provider.is_directml_available()
    return {
        "service": "singing-digital-human",
        "version": "0.1.0",
        "log_level": settings.log_level,
        "data_dir": str(settings.data_dir),
        "models_dir": str(settings.models_dir),
        "max_upload_mb": int(settings.max_upload_mb),
        "max_upload_bytes": int(settings.max_upload_mb) * 1024 * 1024,
        "cors_allow_origins": list(settings.cors_allow_origins),
        "request_id": rid,
        "gpu": {
            "count": len(gpus),
            "devices": gpus,
        },
        "directml": {
            "available": dml_ok,
            "reason": dml_reason,
            "cpu_fallback_enabled": False,
        },
        "onnx_provider": {
            "chosen": "dml" if dml_ok else "unavailable",
            "providers": ["DmlExecutionProvider"] if dml_ok else [],
        },
    }


@router.get("/health", tags=["system"])
async def health(request: Request) -> Any:
    rid = get_request_id()
    payload = _build_payload(rid)
    dml_ok = payload["directml"]["available"]
    payload["status"] = "ok" if dml_ok else "unavailable"
    if not dml_ok:
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.get("/system/info", tags=["system"])
async def system_info(request: Request) -> Any:
    rid = get_request_id()
    payload = _build_payload(rid)
    dml_ok = payload["directml"]["available"]
    payload["status"] = "ok" if dml_ok else "unavailable"
    if not dml_ok:
        return JSONResponse(status_code=503, content=payload)
    return payload
