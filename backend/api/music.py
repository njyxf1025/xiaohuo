from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from core.config import get_settings
from core.logging import get_logger
from core.request_id import get_request_id
from models.schemas import (
    AudioSliceRequest,
    AudioSliceResponse,
    ChorusDetectResponse,
    MusicMetadataResponse,
    MusicUploadResponse,
    WaveformResponse,
)
from services import audio_utils
from services.music_service import DEFAULT_PEAKS, get_music_service
from utils import files as file_utils

_logger = get_logger("api.music")

router = APIRouter()


def _error_response(
    request: Request,
    status_code: int,
    error: str,
    message: str,
    stage: str = "music",
) -> JSONResponse:
    rid = get_request_id()
    _logger.warning(
        f"music error: {error}",
        extra={
            "stage": stage,
            "status_code": status_code,
            "error": error,
            "err_message": message,
        },
    )
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "message": message, "request_id": rid},
    )


def _record_to_response(record) -> MusicUploadResponse:
    return MusicUploadResponse(
        music_id=record.music_id,
        filename=record.filename,
        duration_sec=float(record.duration_sec),
        sample_rate=int(record.sample_rate),
        channels=int(record.channels),
        chorus=record.chorus,
        status=record.status,
    )


def _record_to_metadata(record) -> MusicMetadataResponse:
    return MusicMetadataResponse(
        music_id=record.music_id,
        filename=record.filename,
        extension=record.extension,
        size_bytes=int(record.size_bytes),
        mime_type=record.mime_type,
        duration_sec=float(record.duration_sec),
        sample_rate=int(record.sample_rate),
        channels=int(record.channels),
        status=record.status,
        chorus=record.chorus,
        created_at=float(record.created_at),
    )


@router.post("/music/upload", tags=["music"])
async def upload_music(
    request: Request,
    file: UploadFile = File(..., description="Audio file (mp3/wav/m4a/flac)."),
) -> Any:
    settings = get_settings()
    max_bytes = int(settings.max_upload_mb) * 1024 * 1024
    service = get_music_service()

    filename = file.filename or "upload.bin"
    content_type = file.content_type
    _, ext = file_utils.split_ext(filename)
    if not ext and content_type:
        ext = service._resolve_extension(filename, content_type)
    if not audio_utils.is_supported_extension(ext):
        return _error_response(
            request,
            400,
            "unsupported_format",
            f"unsupported file extension: .{ext}",
        )
    if content_type and not audio_utils.is_supported_mime(content_type):
        return _error_response(
            request,
            415,
            "unsupported_mime",
            f"unsupported mime type: {content_type}",
        )

    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                return _error_response(
                    request,
                    413,
                    "file_too_large",
                    f"file exceeds MAX_UPLOAD_MB={settings.max_upload_mb}",
                )
            chunks.append(chunk)
    finally:
        await file.close()

    if not chunks:
        return _error_response(request, 400, "empty_file", "uploaded file is empty")

    payload = b"".join(chunks)
    try:
        record = await service.upload(
            filename=filename,
            content_type=content_type,
            data=payload,
        )
    except ValueError as exc:
        return _error_response(request, 400, "bad_request", str(exc), stage="music.upload")
    except Exception as exc:
        _logger.exception("music upload crashed: %s", exc)
        return _error_response(
            request,
            500,
            "upload_failed",
            "failed to save uploaded file",
            stage="music.upload",
        )

    try:
        await service.schedule_chorus_detection(record.music_id)
    except Exception as exc:
        _logger.warning("could not schedule chorus detection: %s", exc)

    return _record_to_response(record)


@router.get("/music/slice/{slice_id}/download", tags=["music"])
async def download_slice(slice_id: str, request: Request) -> Any:
    service = get_music_service()
    rec = service.get_slice(slice_id)
    if rec is None:
        return _error_response(request, 404, "slice_not_found", f"slice_id={slice_id} not found")
    path = Path(rec.file_path)
    if not path.exists():
        return _error_response(request, 404, "slice_file_missing", f"file not found on disk: {path}")
    media_type = _media_type_for_ext(rec.extension)
    return FileResponse(
        path=str(path),
        media_type=media_type,
        filename=path.name,
        headers={"X-Slice-Id": rec.slice_id, "X-Music-Id": rec.music_id},
    )


@router.get("/music/{music_id}", tags=["music"])
async def get_music(music_id: str, request: Request) -> Any:
    service = get_music_service()
    record = service.get_music(music_id)
    if record is None:
        return _error_response(request, 404, "music_not_found", f"music_id={music_id} not found")
    return _record_to_metadata(record)


@router.post("/music/{music_id}/detect-chorus", tags=["music"])
async def detect_chorus_endpoint(music_id: str, request: Request) -> Any:
    service = get_music_service()
    record = service.get_music(music_id)
    if record is None:
        return _error_response(request, 404, "music_not_found", f"music_id={music_id} not found")
    try:
        segment = await asyncio_run(service, music_id)
    except Exception as exc:
        _logger.exception("chorus detection failed: %s", exc)
        return _error_response(
            request,
            500,
            "chorus_failed",
            "chorus detection failed",
            stage="music.chorus",
        )
    record = service.get_music(music_id)
    return ChorusDetectResponse(
        music_id=music_id,
        chorus=record.chorus if record else segment,
        status=(record.status if record else "ready"),
    )


@router.post("/music/{music_id}/slice", tags=["music"])
async def slice_music(music_id: str, payload: AudioSliceRequest, request: Request) -> Any:
    service = get_music_service()
    record = service.get_music(music_id)
    if record is None:
        return _error_response(request, 404, "music_not_found", f"music_id={music_id} not found")
    if payload.end_sec <= payload.start_sec:
        return _error_response(
            request,
            400,
            "bad_range",
            "end_sec must be greater than start_sec",
            stage="music.slice",
        )
    if payload.start_sec < 0:
        return _error_response(
            request,
            400,
            "bad_range",
            "start_sec must be non-negative",
            stage="music.slice",
        )
    try:
        slice_record = await asyncio_run_slice(
            service,
            music_id,
            float(payload.start_sec),
            float(payload.end_sec),
            payload.format,
        )
    except FileNotFoundError as exc:
        return _error_response(request, 404, "music_not_found", str(exc), stage="music.slice")
    except ValueError as exc:
        return _error_response(request, 400, "bad_range", str(exc), stage="music.slice")
    except Exception as exc:
        _logger.exception("slicing failed: %s", exc)
        return _error_response(
            request,
            500,
            "slice_failed",
            "audio slicing failed",
            stage="music.slice",
        )
    duration = max(0.0, float(slice_record.end_sec) - float(slice_record.start_sec))
    download_url = f"/api/v1/music/slice/{slice_record.slice_id}/download"
    return AudioSliceResponse(
        slice_id=slice_record.slice_id,
        music_id=slice_record.music_id,
        start_sec=float(slice_record.start_sec),
        end_sec=float(slice_record.end_sec),
        file_path=slice_record.file_path,
        download_url=download_url,
        duration_sec=duration,
    )


@router.get("/music/{music_id}/waveform", tags=["music"])
async def waveform_endpoint(
    music_id: str,
    request: Request,
    num_peaks: int = Query(DEFAULT_PEAKS, ge=50, le=20000),
) -> Any:
    service = get_music_service()
    record = service.get_music(music_id)
    if record is None:
        return _error_response(request, 404, "music_not_found", f"music_id={music_id} not found")
    try:
        data = await asyncio_run_waveform(service, music_id, num_peaks)
    except Exception as exc:
        _logger.exception("waveform failed: %s", exc)
        return _error_response(
            request,
            500,
            "waveform_failed",
            "waveform generation failed",
            stage="music.waveform",
        )
    if data is None:
        return _error_response(request, 404, "music_not_found", f"music_id={music_id} not found")
    return WaveformResponse(**data)


@router.get("/music/{music_id}/download", tags=["music"])
async def download_music(music_id: str, request: Request) -> Any:
    service = get_music_service()
    record = service.get_music(music_id)
    if record is None:
        return _error_response(request, 404, "music_not_found", f"music_id={music_id} not found")
    path = Path(record.file_path)
    if not path.exists():
        return _error_response(request, 404, "music_file_missing", f"file not found: {path}")
    media_type = _media_type_for_ext(record.extension)
    return FileResponse(
        path=str(path),
        media_type=media_type,
        filename=record.filename or path.name,
        headers={"X-Music-Id": music_id},
    )


def _media_type_for_ext(ext: str) -> str:
    e = (ext or "").lower().lstrip(".")
    return {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
        "flac": "audio/flac",
        "ogg": "audio/ogg",
        "aac": "audio/aac",
    }.get(e, "application/octet-stream")


async def asyncio_run(service, music_id: str):
    import asyncio

    return await asyncio.to_thread(service.run_chorus_detection_sync, music_id)


async def asyncio_run_slice(service, music_id: str, start: float, end: float, fmt: Optional[str]):
    import asyncio

    return await asyncio.to_thread(service.slice_audio, music_id, start, end, fmt)


async def asyncio_run_waveform(service, music_id: str, num_peaks: int):
    import asyncio

    return await asyncio.to_thread(service.compute_waveform, music_id, num_peaks)


def register_music_routes(app: FastAPI) -> None:
    app.include_router(router, prefix="/api/v1")
