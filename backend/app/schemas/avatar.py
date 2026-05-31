from __future__ import annotations

from pydantic import BaseModel


class FaceDetectionResult(BaseModel):
    face_detected: bool
    face_count: int
    face_locations: list[list[int]]
    warning: str | None = None
    error: str | None = None


class AvatarUploadResponse(BaseModel):
    avatar_id: str
    filename: str
    file_type: str
    preview_url: str
    face_detection: FaceDetectionResult


class AvatarInfo(BaseModel):
    id: str
    name: str
    type: str
    source: str
    preview_url: str
    file_path: str | None = None
    face_detection: FaceDetectionResult | None = None


class AvatarListResponse(BaseModel):
    avatars: list[AvatarInfo]
    total: int
