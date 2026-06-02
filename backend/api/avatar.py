from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from core.logging import get_logger
from core.request_id import get_request_id
from models.avatar_schemas import (
    AvatarListResponse,
    AvatarMetadata,
    AvatarUploadResponse,
    PresetAvatar,
    PresetAvatarListResponse,
)
from services.avatar_service import (
    MAX_IMAGE_BYTES,
    MAX_VIDEO_BYTES,
    AvatarRecord,
    AvatarService,
    PresetAvatarRecord,
    get_avatar_service,
)

_logger = get_logger("api.avatar")

router = APIRouter()


def _error_response(
    request: Request,
    status_code: int,
    error: str,
    message: str,
    stage: str = "avatar",
) -> JSONResponse:
    rid = get_request_id()
    _logger.warning(
        f"avatar error: {error}",
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


def _media_type_for_record(rec: AvatarRecord) -> str:
    ext = (rec.extension or "").lower().lstrip(".")
    if rec.type == "video":
        return {
            "mp4": "video/mp4",
            "mov": "video/quicktime",
        }.get(ext, "application/octet-stream")
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "application/octet-stream")


def _media_type_for_preset(rec: PresetAvatarRecord) -> str:
    ext = (rec.filename.rsplit(".", 1)[-1] if rec.filename else "").lower()
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "application/octet-stream")


def _record_to_metadata(rec: AvatarRecord) -> AvatarMetadata:
    thumb_url = f"/api/v1/avatars/{rec.avatar_id}/thumbnail"
    file_url = f"/api/v1/avatars/{rec.avatar_id}/file"
    return AvatarMetadata(
        avatar_id=rec.avatar_id,
        type=rec.type,
        filename=rec.filename,
        thumbnail_url=thumb_url,
        file_url=file_url,
        face_box=list(rec.face_box) if rec.face_box else None,
        size_bytes=int(rec.size_bytes),
        created_at=float(rec.created_at),
        is_preset=bool(rec.is_preset),
        has_face=rec.has_face,
    )


def _record_to_upload_response(rec: AvatarRecord) -> AvatarUploadResponse:
    thumb_url = f"/api/v1/avatars/{rec.avatar_id}/thumbnail"
    return AvatarUploadResponse(
        avatar_id=rec.avatar_id,
        type=rec.type,
        filename=rec.filename,
        thumbnail_url=thumb_url,
        has_face=rec.has_face,
        face_box=list(rec.face_box) if rec.face_box else None,
    )


def _preset_to_response(rec: PresetAvatarRecord) -> PresetAvatar:
    thumb_url = f"/api/v1/avatars/presets/{rec.preset_id}/thumbnail"
    file_url = f"/api/v1/avatars/presets/{rec.preset_id}/file"
    return PresetAvatar(
        preset_id=rec.preset_id,
        name=rec.name,
        filename=rec.filename,
        thumbnail_url=thumb_url,
        file_url=file_url,
        description=rec.description,
        created_at=float(rec.created_at),
    )


@router.post("/avatars/upload", tags=["avatars"])
async def upload_avatar(
    request: Request,
    file: UploadFile = File(
        ...,
        description="Avatar source (image: jpg/png/webp; video: mp4/mov).",
    ),
) -> Any:
    service = get_avatar_service()

    filename = file.filename or "upload.bin"
    content_type = file.content_type

    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_VIDEO_BYTES:
                return _error_response(
                    request,
                    413,
                    "file_too_large",
                    f"file exceeds max size ({MAX_VIDEO_BYTES} bytes)",
                    stage="avatar.upload",
                )
            chunks.append(chunk)
    finally:
        await file.close()

    if not chunks:
        return _error_response(
            request,
            400,
            "empty_file",
            "uploaded file is empty",
            stage="avatar.upload",
        )

    payload = b"".join(chunks)

    ext = Path(filename).suffix.lower().lstrip(".")
    if not ext and content_type:
        ext = AvatarService.extension_from_mime(content_type)
    ext = (ext or "").lower().lstrip(".")
    kind = AvatarService.resolve_kind(ext, content_type)
    if kind is None:
        return _error_response(
            request,
            400,
            "unsupported_format",
            f"unsupported file extension: .{ext}",
            stage="avatar.upload",
        )
    if kind == "image" and len(payload) > MAX_IMAGE_BYTES:
        return _error_response(
            request,
            413,
            "file_too_large",
            f"image exceeds {MAX_IMAGE_BYTES} bytes (10 MB)",
            stage="avatar.upload",
        )
    if kind == "video" and len(payload) > MAX_VIDEO_BYTES:
        return _error_response(
            request,
            413,
            "file_too_large",
            f"video exceeds {MAX_VIDEO_BYTES} bytes (50 MB)",
            stage="avatar.upload",
        )

    try:
        record = await service.upload(
            filename=filename,
            content_type=content_type,
            data=payload,
        )
    except ValueError as exc:
        msg = str(exc)
        if "too large" in msg:
            return _error_response(
                request,
                413,
                "file_too_large",
                msg,
                stage="avatar.upload",
            )
        if "unsupported" in msg:
            return _error_response(
                request,
                400,
                "unsupported_format",
                msg,
                stage="avatar.upload",
            )
        return _error_response(
            request,
            400,
            "no_face_detected",
            msg,
            stage="avatar.upload",
        )
    except Exception as exc:
        _logger.exception("avatar upload crashed: %s", exc)
        return _error_response(
            request,
            500,
            "upload_failed",
            "failed to save uploaded avatar",
            stage="avatar.upload",
        )

    return _record_to_upload_response(record)


@router.get("/avatars/presets", tags=["avatars"])
async def list_presets(request: Request) -> Any:
    service = get_avatar_service()
    presets = service.list_presets()
    return PresetAvatarListResponse(
        presets=[_preset_to_response(p) for p in presets],
        count=len(presets),
    )


@router.get("/avatars/presets/{preset_id}/thumbnail", tags=["avatars"])
async def preset_thumbnail(preset_id: str, request: Request) -> Any:
    service = get_avatar_service()
    path = service.preset_thumbnail_path(preset_id)
    if path is None:
        return _error_response(
            request,
            404,
            "preset_not_found",
            f"preset_id={preset_id} not found",
            stage="avatar.presets",
        )
    media_type = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return FileResponse(
        path=str(path),
        media_type=media_type,
        filename=path.name,
        headers={"X-Preset-Id": preset_id},
    )


@router.get("/avatars/presets/{preset_id}/file", tags=["avatars"])
async def preset_file(preset_id: str, request: Request) -> Any:
    service = get_avatar_service()
    path = service.preset_file_path(preset_id)
    rec = service.get_preset(preset_id)
    if path is None or rec is None:
        return _error_response(
            request,
            404,
            "preset_not_found",
            f"preset_id={preset_id} not found",
            stage="avatar.presets",
        )
    return FileResponse(
        path=str(path),
        media_type=_media_type_for_preset(rec),
        filename=path.name,
        headers={"X-Preset-Id": preset_id},
    )


@router.get("/avatars", tags=["avatars"])
async def list_avatars(request: Request) -> Any:
    service = get_avatar_service()
    records = service.list_avatars()
    return AvatarListResponse(
        avatars=[_record_to_metadata(r) for r in records],
        count=len(records),
    )


@router.get("/avatars/{avatar_id}", tags=["avatars"])
async def get_avatar(avatar_id: str, request: Request) -> Any:
    service = get_avatar_service()
    rec = service.get_avatar(avatar_id)
    if rec is None:
        return _error_response(
            request,
            404,
            "avatar_not_found",
            f"avatar_id={avatar_id} not found",
            stage="avatar",
        )
    return _record_to_metadata(rec)


@router.get("/avatars/{avatar_id}/thumbnail", tags=["avatars"])
async def get_avatar_thumbnail(avatar_id: str, request: Request) -> Any:
    service = get_avatar_service()
    rec = service.get_avatar(avatar_id)
    if rec is None:
        return _error_response(
            request,
            404,
            "avatar_not_found",
            f"avatar_id={avatar_id} not found",
            stage="avatar.thumbnail",
        )
    path = Path(rec.thumbnail_path)
    if not path.exists():
        return _error_response(
            request,
            404,
            "thumbnail_missing",
            f"thumbnail missing on disk: {path}",
            stage="avatar.thumbnail",
        )
    return FileResponse(
        path=str(path),
        media_type="image/jpeg",
        filename=path.name,
        headers={"X-Avatar-Id": avatar_id},
    )


@router.get("/avatars/{avatar_id}/file", tags=["avatars"])
async def get_avatar_file(avatar_id: str, request: Request) -> Any:
    service = get_avatar_service()
    rec = service.get_avatar(avatar_id)
    if rec is None:
        return _error_response(
            request,
            404,
            "avatar_not_found",
            f"avatar_id={avatar_id} not found",
            stage="avatar.file",
        )
    path = Path(rec.file_path)
    if not path.exists():
        return _error_response(
            request,
            404,
            "file_missing",
            f"file missing on disk: {path}",
            stage="avatar.file",
        )
    return FileResponse(
        path=str(path),
        media_type=_media_type_for_record(rec),
        filename=rec.filename or path.name,
        headers={"X-Avatar-Id": avatar_id},
    )


@router.delete("/avatars/{avatar_id}", tags=["avatars"])
async def delete_avatar(avatar_id: str, request: Request) -> Any:
    service = get_avatar_service()
    rec = service.get_avatar(avatar_id)
    if rec is None:
        return _error_response(
            request,
            404,
            "avatar_not_found",
            f"avatar_id={avatar_id} not found",
            stage="avatar.delete",
        )
    try:
        ok = service.delete_avatar(avatar_id)
    except ValueError as exc:
        return _error_response(
            request,
            400,
            "cannot_delete",
            str(exc),
            stage="avatar.delete",
        )
    except Exception as exc:
        _logger.exception("avatar delete crashed: %s", exc)
        return _error_response(
            request,
            500,
            "delete_failed",
            "failed to delete avatar",
            stage="avatar.delete",
        )
    if not ok:
        return _error_response(
            request,
            404,
            "avatar_not_found",
            f"avatar_id={avatar_id} not found",
            stage="avatar.delete",
        )
    rid = get_request_id()
    return {"deleted": True, "avatar_id": avatar_id, "request_id": rid}


def register_avatar_routes(app: FastAPI) -> None:
    app.include_router(router, prefix="/api/v1")
