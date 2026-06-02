from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


AvatarTypeStr = Literal["image", "video"]


class FaceBox(BaseModel):
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    w: int = Field(..., ge=0)
    h: int = Field(..., ge=0)

    def as_list(self) -> List[int]:
        return [int(self.x), int(self.y), int(self.w), int(self.h)]


class AvatarMetadata(BaseModel):
    avatar_id: str
    type: AvatarTypeStr
    filename: str
    thumbnail_url: str
    file_url: Optional[str] = None
    face_box: Optional[List[int]] = None
    size_bytes: int = 0
    created_at: float = 0.0
    is_preset: bool = False
    has_face: Optional[bool] = None


class AvatarUploadResponse(BaseModel):
    avatar_id: str
    type: AvatarTypeStr
    filename: str
    thumbnail_url: str
    has_face: Optional[bool] = None
    face_box: Optional[List[int]] = None


class AvatarListResponse(BaseModel):
    avatars: List[AvatarMetadata]
    count: int


class PresetAvatar(BaseModel):
    preset_id: str
    name: str
    filename: str
    thumbnail_url: str
    file_url: Optional[str] = None
    description: Optional[str] = None
    created_at: float = 0.0


class PresetAvatarListResponse(BaseModel):
    presets: List[PresetAvatar]
    count: int


class AvatarErrorPayload(BaseModel):
    error: str
    message: str
    request_id: Optional[str] = None
