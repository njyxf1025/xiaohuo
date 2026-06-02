from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from core import gpu, onnx_provider
from core.request_id import get_request_id

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    rid = get_request_id()
    try:
        gpus = gpu.detect_gpus()
    except Exception:
        gpus = []
    try:
        providers, label = onnx_provider.select_providers()
    except Exception:
        providers, label = (["CPUExecutionProvider"], "cpu-fallback")
    return {
        "status": "ok",
        "request_id": rid,
        "gpu": {
            "count": len(gpus),
            "devices": gpus,
        },
        "onnx_provider": {
            "chosen": label,
            "providers": providers,
        },
    }


@router.get("/system/info")
async def system_info(request: Request) -> dict[str, Any]:
    rid = get_request_id()
    try:
        gpus = gpu.detect_gpus()
    except Exception:
        gpus = []
    try:
        providers, label = onnx_provider.select_providers()
    except Exception:
        providers, label = (["CPUExecutionProvider"], "cpu-fallback")
    return {
        "request_id": rid,
        "gpu": {
            "count": len(gpus),
            "devices": gpus,
        },
        "onnx_provider": {
            "chosen": label,
            "providers": providers,
        },
    }
