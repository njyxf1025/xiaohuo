from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from core import gpu, onnx_provider
from core.request_id import get_request_id
from core.onnx_provider import DirectMLNotAvailable

router = APIRouter()


def _build_payload(rid: str) -> dict[str, Any]:
    try:
        gpus = gpu.detect_gpus()
    except Exception:
        gpus = []
    dml_ok, dml_reason = onnx_provider.is_directml_available()
    return {
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


@router.get("/health")
async def health(request: Request) -> Any:
    rid = get_request_id()
    payload = _build_payload(rid)
    dml_ok = payload["directml"]["available"]
    payload["status"] = "ok" if dml_ok else "unavailable"
    if not dml_ok:
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.get("/system/info")
async def system_info(request: Request) -> Any:
    rid = get_request_id()
    payload = _build_payload(rid)
    dml_ok = payload["directml"]["available"]
    payload["status"] = "ok" if dml_ok else "unavailable"
    if not dml_ok:
        return JSONResponse(status_code=503, content=payload)
    return payload
