from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.logger import logger
from app.schemas.avatar import (
    AvatarInfo,
    AvatarListResponse,
    AvatarUploadResponse,
    FaceDetectionResult,
)
from app.services import avatar_service

router = APIRouter(prefix="/api/avatar", tags=["avatar"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}
ALLOWED_VIDEO_TYPES = {"video/mp4"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_VIDEO_SIZE = 100 * 1024 * 1024


@router.post("/upload", response_model=AvatarUploadResponse)
async def upload_avatar(file: UploadFile = File(...)):
    content_type = file.content_type or ""
    if content_type in ALLOWED_IMAGE_TYPES:
        max_size = MAX_IMAGE_SIZE
        file_category = "image"
    elif content_type in ALLOWED_VIDEO_TYPES:
        max_size = MAX_VIDEO_SIZE
        file_category = "video"
    else:
        logger.warning(f"不支持的文件类型: {content_type}")
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {content_type}，仅支持 JPG/PNG 图片和 MP4 视频",
        )

    contents = await file.read()
    if len(contents) > max_size:
        size_mb = max_size // (1024 * 1024)
        logger.warning(f"文件大小超过限制: {file_category} {len(contents)} > {max_size}")
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制，{file_category}最大允许{size_mb}MB",
        )

    suffix = Path(file.filename or "").suffix or (
        ".jpg" if file_category == "image" else ".mp4"
    )
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        meta = avatar_service.save_avatar(tmp_path, content_type, file.filename or "unknown")
    finally:
        tmp_path.unlink(missing_ok=True)

    face_result = FaceDetectionResult(**meta["face_detection"])
    return AvatarUploadResponse(
        avatar_id=meta["id"],
        filename=meta["name"],
        file_type=meta["type"],
        preview_url=meta["preview_url"],
        face_detection=face_result,
    )


@router.get("/list", response_model=AvatarListResponse)
async def list_avatars():
    preset_avatars = avatar_service.get_preset_avatars()
    custom_avatars = avatar_service.get_all_custom_avatars()
    all_avatars = []
    for a in preset_avatars:
        all_avatars.append(
            AvatarInfo(
                id=a["id"],
                name=a["name"],
                type="preset",
                source="preset",
                preview_url=a["preview_url"],
                file_path=a.get("image_path"),
            )
        )
    for a in custom_avatars:
        face_result = None
        if a.get("face_detection"):
            face_result = FaceDetectionResult(**a["face_detection"])
        all_avatars.append(
            AvatarInfo(
                id=a["id"],
                name=a["name"],
                type=a.get("type", "custom"),
                source="custom",
                preview_url=a["preview_url"],
                file_path=a.get("file_path"),
                face_detection=face_result,
            )
        )
    return AvatarListResponse(avatars=all_avatars, total=len(all_avatars))


@router.get("/{avatar_id}", response_model=AvatarInfo)
async def get_avatar(avatar_id: str):
    preset = avatar_service.get_preset_avatar(avatar_id)
    if preset:
        return AvatarInfo(
            id=preset["id"],
            name=preset["name"],
            type="preset",
            source="preset",
            preview_url=preset["preview_url"],
            file_path=preset.get("image_path"),
        )
    custom = avatar_service.get_custom_avatar(avatar_id)
    if custom:
        face_result = None
        if custom.get("face_detection"):
            face_result = FaceDetectionResult(**custom["face_detection"])
        return AvatarInfo(
            id=custom["id"],
            name=custom["name"],
            type=custom.get("type", "custom"),
            source="custom",
            preview_url=custom["preview_url"],
            file_path=custom.get("file_path"),
            face_detection=face_result,
        )
    raise HTTPException(status_code=404, detail="形象不存在")


@router.get("/{avatar_id}/preview")
async def get_avatar_preview(avatar_id: str):
    preset = avatar_service.get_preset_avatar(avatar_id)
    if preset:
        image_path = Path(preset["image_path"])
        if image_path.exists():
            return FileResponse(image_path, media_type="image/png")
        raise HTTPException(status_code=404, detail="预设形象文件不存在")
    custom = avatar_service.get_custom_avatar(avatar_id)
    if custom:
        file_path = Path(custom.get("file_path", ""))
        if file_path.exists():
            if custom["type"].startswith("video"):
                return FileResponse(file_path, media_type=custom["type"])
            return FileResponse(file_path, media_type=custom["type"])
        raise HTTPException(status_code=404, detail="形象文件不存在")
    raise HTTPException(status_code=404, detail="形象不存在")


@router.delete("/{avatar_id}")
async def delete_avatar(avatar_id: str):
    preset = avatar_service.get_preset_avatar(avatar_id)
    if preset:
        raise HTTPException(status_code=400, detail="预设形象不可删除")
    deleted = avatar_service.delete_custom_avatar(avatar_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="形象不存在")
    return {"message": "删除成功", "avatar_id": avatar_id}
