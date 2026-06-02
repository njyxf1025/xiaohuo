from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from core.logging import get_logger
from core.request_id import get_request_id
from models.generation_schemas import (
    GenerationRequest,
    GenerationResponse,
    TaskListResponse,
    TaskState,
    TaskStatusResponse,
)
from services.generation_service import (
    SUPPORTED_MODELS,
    GenerationService,
    _resolve_model_name,
    get_generation_service,
)
from services.musetalk_engine import MuseTalkDirectMLNotAvailable
from services.task_manager import get_task_manager
from services.vocal_separation import (
    VocalSeparationDirectMLNotAvailable,
    get_vocal_separator,
)
from services.wav2lip_engine import (
    Wav2LipDirectMLNotAvailable,
    Wav2LipEngine,
    Wav2LipModelNotLoaded,
)

_logger = get_logger("api.generation")

router = APIRouter()


def _error_response(
    request: Request,
    status_code: int,
    error: str,
    message: str,
    stage: str = "generation",
    task_id: Optional[str] = None,
) -> JSONResponse:
    rid = get_request_id()
    _logger.warning(
        f"generation error: {error}",
        extra={
            "stage": stage,
            "status_code": status_code,
            "error": error,
            "err_message": message,
            "task_id": task_id or "-",
        },
    )
    payload = {"error": error, "message": message, "request_id": rid}
    if task_id:
        payload["task_id"] = task_id
    return JSONResponse(status_code=status_code, content=payload)


def _record_to_status(record: Optional[dict]) -> Optional[TaskStatusResponse]:
    if record is None:
        return None
    try:
        return TaskStatusResponse(**record)
    except Exception as exc:
        _logger.warning("status serialization failed: %s", exc)
        return None


def _validate_payload(request: Request, payload: GenerationRequest) -> Optional[JSONResponse]:
    if not payload.has_audio_ref():
        return _error_response(
            request,
            400,
            "bad_request",
            "either music_id or slice_id is required",
            stage="generation.create",
        )
    if payload.avatar_type == "preset" and not payload.preset_id:
        return _error_response(
            request,
            400,
            "bad_request",
            "preset_id is required when avatar_type='preset'",
            stage="generation.create",
        )
    if payload.avatar_type in ("image", "video") and not payload.avatar_id:
        return _error_response(
            request,
            400,
            "bad_request",
            f"avatar_id is required when avatar_type='{payload.avatar_type}'",
            stage="generation.create",
        )
    if payload.slice_id and (payload.start_sec is not None or payload.end_sec is not None):
        return _error_response(
            request,
            400,
            "bad_request",
            "start_sec/end_sec must be omitted when slice_id is provided",
            stage="generation.create",
        )
    if not payload.slice_id:
        if payload.start_sec is None or payload.end_sec is None:
            return _error_response(
                request,
                400,
                "bad_request",
                "start_sec and end_sec are required when slice_id is missing",
                stage="generation.create",
            )
        if float(payload.end_sec) <= float(payload.start_sec):
            return _error_response(
                request,
                400,
                "bad_range",
                "end_sec must be greater than start_sec",
                stage="generation.create",
            )
    return None


def _dispatch_generation(
    request: Request,
    payload: GenerationRequest,
    rid: str,
    forced_model: Optional[str] = None,
):
    service = get_generation_service()
    try:
        task_id = service.start_generation(payload, request_id=rid)
    except Wav2LipDirectMLNotAvailable as exc:
        return _error_response(
            request,
            503,
            "directml_unavailable",
            str(exc),
            stage="generation.create",
        )
    except MuseTalkDirectMLNotAvailable as exc:
        return _error_response(
            request,
            503,
            "directml_unavailable",
            str(exc),
            stage="generation.create",
        )
    except Wav2LipModelNotLoaded as exc:
        return _error_response(
            request,
            503,
            "model_not_loaded",
            str(exc),
            stage="generation.create",
        )
    except FileNotFoundError as exc:
        return _error_response(
            request,
            404,
            "source_not_found",
            str(exc),
            stage="generation.create",
        )
    except ValueError as exc:
        return _error_response(
            request,
            400,
            "bad_request",
            str(exc),
            stage="generation.create",
        )
    except Exception as exc:
        _logger.exception("start_generation crashed: %s", exc)
        return _error_response(
            request,
            500,
            "start_failed",
            "failed to start generation",
            stage="generation.create",
        )
    return service, task_id


@router.post("/generation", tags=["generation"])
async def create_generation(
    request: Request,
    payload: GenerationRequest,
) -> Any:
    rid = get_request_id()
    err = _validate_payload(request, payload)
    if err is not None:
        return err
    dispatched = _dispatch_generation(request, payload, rid)
    if isinstance(dispatched, JSONResponse):
        return dispatched
    service, task_id = dispatched
    record = service.get_record(task_id)
    if record is None:
        return _error_response(
            request,
            500,
            "task_creation_failed",
            "task id was returned but no record was found",
            stage="generation.create",
            task_id=task_id,
        )
    status_resp = _record_to_status(record)
    if status_resp is None:
        return _error_response(
            request,
            500,
            "task_serialization_failed",
            "task record could not be serialized",
            stage="generation.create",
            task_id=task_id,
        )
    return GenerationResponse(
        task_id=task_id,
        status=TaskState(status_resp.status),
        message="task accepted",
        websocket_url=f"/api/v1/generation/{task_id}/ws",
        request_id=rid,
    )


@router.post("/generation/wav2lip", tags=["generation"])
async def create_generation_wav2lip(
    request: Request,
    payload: GenerationRequest,
) -> Any:
    rid = get_request_id()
    err = _validate_payload(request, payload)
    if err is not None:
        return err
    payload_dict = payload.model_dump()
    payload_dict["model"] = "wav2lip"
    locked = GenerationRequest(**payload_dict)
    dispatched = _dispatch_generation(request, locked, rid, forced_model="wav2lip")
    if isinstance(dispatched, JSONResponse):
        return dispatched
    service, task_id = dispatched
    record = service.get_record(task_id)
    status_resp = _record_to_status(record) if record else None
    return GenerationResponse(
        task_id=task_id,
        status=TaskState(status_resp.status) if status_resp else TaskState.PENDING,
        message="wav2lip task accepted",
        websocket_url=f"/api/v1/generation/{task_id}/ws",
        request_id=rid,
    )


@router.post("/generation/musetalk", tags=["generation"])
async def create_generation_musetalk(
    request: Request,
    payload: GenerationRequest,
) -> Any:
    rid = get_request_id()
    err = _validate_payload(request, payload)
    if err is not None:
        return err
    payload_dict = payload.model_dump()
    payload_dict["model"] = "musetalk"
    locked = GenerationRequest(**payload_dict)
    dispatched = _dispatch_generation(request, locked, rid, forced_model="musetalk")
    if isinstance(dispatched, JSONResponse):
        return dispatched
    service, task_id = dispatched
    record = service.get_record(task_id)
    status_resp = _record_to_status(record) if record else None
    return GenerationResponse(
        task_id=task_id,
        status=TaskState(status_resp.status) if status_resp else TaskState.PENDING,
        message="musetalk task accepted (step-2 deliverable — currently routes to skeleton)",
        websocket_url=f"/api/v1/generation/{task_id}/ws",
        request_id=rid,
    )


@router.get("/generation", tags=["generation"])
async def list_generations(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    service = get_generation_service()
    try:
        records = service.list_records(limit=limit)
    except Exception as exc:
        _logger.exception("list_generations crashed: %s", exc)
        return _error_response(
            request, 500, "list_failed", "failed to list tasks", stage="generation.list"
        )
    items: list[TaskStatusResponse] = []
    for rec in records:
        s = _record_to_status(rec)
        if s is not None:
            items.append(s)
    return TaskListResponse(tasks=items, count=len(items), limit=limit)


@router.get("/generation/{task_id}", tags=["generation"])
async def get_generation(request: Request, task_id: str) -> Any:
    service = get_generation_service()
    record = service.get_record(task_id)
    if record is None:
        return _error_response(
            request,
            404,
            "task_not_found",
            f"task_id={task_id} not found",
            stage="generation.status",
            task_id=task_id,
        )
    status_resp = _record_to_status(record)
    if status_resp is None:
        return _error_response(
            request,
            500,
            "task_serialization_failed",
            "task record could not be serialized",
            stage="generation.status",
            task_id=task_id,
        )
    return status_resp


@router.delete("/generation/{task_id}", tags=["generation"])
async def cancel_generation(request: Request, task_id: str) -> Any:
    service = get_generation_service()
    manager = get_task_manager()
    rec = manager.get_task(task_id)
    if rec is None:
        return _error_response(
            request,
            404,
            "task_not_found",
            f"task_id={task_id} not found",
            stage="generation.cancel",
            task_id=task_id,
        )
    if rec.status.value in (TaskState.SUCCESS.value, TaskState.FAILED.value, TaskState.CANCELLED.value):
        return _error_response(
            request,
            409,
            "task_not_active",
            f"task already in terminal state: {rec.status.value}",
            stage="generation.cancel",
            task_id=task_id,
        )
    ok = service.cancel(task_id)
    rid = get_request_id()
    return {"task_id": task_id, "cancelled": bool(ok), "request_id": rid}


@router.get("/generation/{task_id}/download", tags=["generation"])
async def download_generation(request: Request, task_id: str) -> Any:
    service = get_generation_service()
    record = service.get_record(task_id)
    if record is None:
        return _error_response(
            request,
            404,
            "task_not_found",
            f"task_id={task_id} not found",
            stage="generation.download",
            task_id=task_id,
        )
    if record.get("status") != TaskState.SUCCESS.value:
        return _error_response(
            request,
            409,
            "task_not_ready",
            f"task status: {record.get('status')}",
            stage="generation.download",
            task_id=task_id,
        )
    result = record.get("result") or {}
    path_str = result.get("output_path")
    if not path_str:
        return _error_response(
            request,
            500,
            "result_missing",
            "task succeeded but output_path is empty",
            stage="generation.download",
            task_id=task_id,
        )
    path = Path(path_str)
    if not path.exists():
        return _error_response(
            request,
            404,
            "output_missing",
            f"output not found on disk: {path}",
            stage="generation.download",
            task_id=task_id,
        )
    return FileResponse(
        path=str(path),
        media_type="video/mp4",
        filename=path.name,
        headers={
            "X-Task-Id": task_id,
            "X-Request-Id": get_request_id(),
            "X-Duration-Sec": str(result.get("duration_sec") or 0),
            "X-Fps": str(result.get("fps") or 0),
        },
    )


@router.get("/generation/{task_id}/thumbnail", tags=["generation"])
async def thumbnail_generation(request: Request, task_id: str) -> Any:
    service = get_generation_service()
    record = service.get_record(task_id)
    if record is None:
        return _error_response(
            request,
            404,
            "task_not_found",
            f"task_id={task_id} not found",
            stage="generation.thumbnail",
            task_id=task_id,
        )
    result = record.get("result") or {}
    path_str = result.get("thumbnail_path")
    if not path_str:
        candidate = service.output_thumbnail_path(task_id)
        if candidate.exists():
            path = candidate
        else:
            return _error_response(
                request,
                404,
                "thumbnail_missing",
                "thumbnail not available for this task",
                stage="generation.thumbnail",
                task_id=task_id,
            )
    else:
        path = Path(path_str)
    if not path.exists():
        return _error_response(
            request,
            404,
            "thumbnail_missing",
            f"thumbnail not on disk: {path}",
            stage="generation.thumbnail",
            task_id=task_id,
        )
    return FileResponse(
        path=str(path),
        media_type="image/jpeg",
        filename=path.name,
        headers={"X-Task-Id": task_id, "X-Request-Id": get_request_id()},
    )


@router.get("/generation/engines/status", tags=["generation"])
async def engines_status(request: Request) -> Any:
    service = get_generation_service()
    status = service.engine_status()
    payload = {
        "engines": status,
        "supported_models": list(SUPPORTED_MODELS),
        "default_model": "wav2lip",
        "cpu_fallback_enabled": False,
        "request_id": get_request_id(),
        "timestamp": time.time(),
    }
    wav2lip_ok = bool(status.get("wav2lip", {}).get("directml_ready"))
    musetalk_ok = bool(status.get("musetalk", {}).get("directml_ready"))
    # /generation/engines/status is consumed by the front-end on every
    # Generate page render. Return 200 with a `ready` flag so the UI can
    # show engine status without triggering a red toast on every refresh.
    payload["ready"] = wav2lip_ok or musetalk_ok
    payload["degraded"] = not payload["ready"]
    return payload


@router.post("/generation/engines/wav2lip/warmup", tags=["generation"])
async def engine_wav2lip_warmup(request: Request) -> Any:
    service = get_generation_service()
    status = service.engine_status().get("wav2lip", {})
    dml_ok = bool(status.get("directml_ready"))
    if not dml_ok:
        payload = {
            "ok": False,
            "model": "wav2lip",
            "directml_available": False,
            "directml_reason": status.get("directml_reason"),
            "cpu_fallback_enabled": False,
            "request_id": get_request_id(),
            "timestamp": time.time(),
        }
        return JSONResponse(status_code=503, content=payload)
    try:
        ok = service.warmup_engine("wav2lip")
    except Wav2LipDirectMLNotAvailable as exc:
        payload = {
            "ok": False,
            "model": "wav2lip",
            "directml_available": False,
            "directml_reason": str(exc),
            "cpu_fallback_enabled": False,
            "last_error": str(exc),
            "request_id": get_request_id(),
            "timestamp": time.time(),
        }
        return JSONResponse(status_code=503, content=payload)
    fresh = service.engine_status().get("wav2lip", {})
    payload = {
        "ok": bool(ok),
        "model": "wav2lip",
        "loaded": bool(fresh.get("loaded")),
        "directml_available": dml_ok,
        "provider_label": fresh.get("provider_label", "-"),
        "providers": fresh.get("providers", []),
        "last_error": fresh.get("last_error"),
        "paths": fresh.get("paths", {}),
        "request_id": get_request_id(),
        "timestamp": time.time(),
    }
    if not ok:
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.post("/generation/engines/musetalk/warmup", tags=["generation"])
async def engine_musetalk_warmup(request: Request) -> Any:
    service = get_generation_service()
    status = service.engine_status().get("musetalk", {})
    dml_ok = bool(status.get("directml_ready"))
    if not dml_ok:
        payload = {
            "ok": False,
            "model": "musetalk",
            "directml_available": False,
            "directml_reason": status.get("directml_reason"),
            "cpu_fallback_enabled": False,
            "request_id": get_request_id(),
            "timestamp": time.time(),
        }
        return JSONResponse(status_code=503, content=payload)
    try:
        ok = service.warmup_engine("musetalk")
    except MuseTalkDirectMLNotAvailable as exc:
        payload = {
            "ok": False,
            "model": "musetalk",
            "directml_available": False,
            "directml_reason": str(exc),
            "cpu_fallback_enabled": False,
            "last_error": str(exc),
            "request_id": get_request_id(),
            "timestamp": time.time(),
        }
        return JSONResponse(status_code=503, content=payload)
    fresh = service.engine_status().get("musetalk", {})
    payload = {
        "ok": bool(ok),
        "model": "musetalk",
        "loaded": bool(fresh.get("loaded")),
        "directml_available": dml_ok,
        "provider_label": fresh.get("provider_label", "-"),
        "providers": fresh.get("providers", []),
        "last_error": fresh.get("last_error"),
        "paths": fresh.get("paths", {}),
        "request_id": get_request_id(),
        "timestamp": time.time(),
    }
    if not ok:
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.get("/generation/engine/status", tags=["generation"])
async def engine_status(request: Request) -> Any:
    engine = Wav2LipEngine.instance()
    paths = engine.model_paths()
    dml_ok, dml_reason = engine.is_directml_ready()
    separator = get_vocal_separator()
    sep_paths = separator.model_paths()
    payload = {
        "loaded": engine.is_loaded(),
        "directml_available": dml_ok,
        "directml_reason": dml_reason,
        "cpu_fallback_enabled": False,
        "providers": engine.providers(),
        "provider_label": engine.provider_label(),
        "wav2lip_path": str(paths.wav2lip_path) if paths and paths.wav2lip_path else None,
        "face_detect_path": str(paths.face_detect_path) if paths and paths.face_detect_path else None,
        "last_error": engine.last_error(),
        "vocal_separation": {
            "loaded": separator.is_loaded(),
            "model_path": str(sep_paths.model_path) if sep_paths else None,
            "model_present": bool(sep_paths and sep_paths.is_complete()),
            "providers": separator.providers(),
        },
        "request_id": get_request_id(),
        "timestamp": time.time(),
    }
    if not dml_ok:
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.post("/generation/engine/warmup", tags=["generation"])
async def engine_warmup(request: Request) -> Any:
    engine = Wav2LipEngine.instance()
    dml_ok, dml_reason = engine.is_directml_ready()
    if not dml_ok:
        payload = {
            "ok": False,
            "loaded": False,
            "directml_available": False,
            "directml_reason": dml_reason,
            "cpu_fallback_enabled": False,
            "providers": [],
            "provider_label": "none",
            "last_error": f"directml_unavailable: {dml_reason}",
            "request_id": get_request_id(),
            "timestamp": time.time(),
        }
        return JSONResponse(status_code=503, content=payload)
    try:
        ok = engine.warmup()
    except Wav2LipDirectMLNotAvailable as exc:
        payload = {
            "ok": False,
            "loaded": False,
            "directml_available": False,
            "directml_reason": str(exc),
            "cpu_fallback_enabled": False,
            "providers": [],
            "provider_label": "none",
            "last_error": str(exc),
            "request_id": get_request_id(),
            "timestamp": time.time(),
        }
        return JSONResponse(status_code=503, content=payload)
    paths = engine.model_paths()
    separator = get_vocal_separator()
    sep_paths = separator.model_paths()
    sep_ok = True
    sep_error: Optional[str] = None
    try:
        sep_ok = separator.warmup()
    except VocalSeparationDirectMLNotAvailable as exc:
        sep_ok = False
        sep_error = str(exc)
    except Exception as exc:
        sep_ok = False
        sep_error = str(exc)
    payload = {
        "ok": bool(ok),
        "loaded": engine.is_loaded(),
        "directml_available": dml_ok,
        "directml_reason": dml_reason,
        "cpu_fallback_enabled": False,
        "providers": engine.providers(),
        "provider_label": engine.provider_label(),
        "wav2lip_path": str(paths.wav2lip_path) if paths and paths.wav2lip_path else None,
        "face_detect_path": str(paths.face_detect_path) if paths and paths.face_detect_path else None,
        "last_error": engine.last_error(),
        "vocal_separation": {
            "ok": bool(sep_ok),
            "loaded": separator.is_loaded(),
            "model_present": bool(sep_paths and sep_paths.is_complete()),
            "model_path": str(sep_paths.model_path) if sep_paths else None,
            "providers": separator.providers(),
            "last_error": separator.last_error() or sep_error,
        },
        "request_id": get_request_id(),
        "timestamp": time.time(),
    }
    if not ok:
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.post("/generation/vocal_separation/warmup", tags=["generation"])
async def vocal_separation_warmup(request: Request) -> Any:
    separator = get_vocal_separator()
    dml_ok, dml_reason = separator.is_directml_ready()
    if not dml_ok:
        payload = {
            "ok": False,
            "loaded": False,
            "model_present": False,
            "directml_available": False,
            "directml_reason": dml_reason,
            "cpu_fallback_enabled": False,
            "providers": [],
            "provider_label": "none",
            "last_error": f"directml_unavailable: {dml_reason}",
            "request_id": get_request_id(),
            "timestamp": time.time(),
        }
        return JSONResponse(status_code=503, content=payload)
    try:
        ok = separator.warmup()
    except VocalSeparationDirectMLNotAvailable as exc:
        payload = {
            "ok": False,
            "loaded": False,
            "directml_available": False,
            "directml_reason": str(exc),
            "cpu_fallback_enabled": False,
            "providers": [],
            "provider_label": "none",
            "last_error": str(exc),
            "request_id": get_request_id(),
            "timestamp": time.time(),
        }
        return JSONResponse(status_code=503, content=payload)
    paths = separator.model_paths()
    payload = {
        "ok": bool(ok),
        "loaded": separator.is_loaded(),
        "model_present": bool(paths and paths.is_complete()),
        "model_path": str(paths.model_path) if paths else None,
        "providers": separator.providers(),
        "provider_label": separator.provider_label(),
        "last_error": separator.last_error(),
        "request_id": get_request_id(),
        "timestamp": time.time(),
    }
    if not ok:
        return JSONResponse(status_code=503, content=payload)
    return payload


def register_generation_routes(app: FastAPI) -> None:
    app.include_router(router, prefix="/api/v1")
