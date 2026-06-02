from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


AvatarType = Literal["image", "video", "preset"]


class SliceRef(BaseModel):
    music_id: Optional[str] = Field(default=None, description="Reference to uploaded music.")
    slice_id: Optional[str] = Field(default=None, description="Reference to a previously created audio slice.")
    start_sec: Optional[float] = Field(default=None, ge=0.0, description="Start second when not using a stored slice.")
    end_sec: Optional[float] = Field(default=None, ge=0.0, description="End second when not using a stored slice.")


class GenerationRequest(BaseModel):
    music_id: Optional[str] = Field(default=None, description="Source music id (when not using a stored slice).")
    slice_id: Optional[str] = Field(default=None, description="Stored audio slice id (preferred).")
    start_sec: Optional[float] = Field(default=None, ge=0.0, description="Audio start second.")
    end_sec: Optional[float] = Field(default=None, ge=0.0, description="Audio end second.")
    avatar_id: Optional[str] = Field(default=None, description="Custom avatar id (image or video).")
    avatar_type: AvatarType = Field(default="image", description="Avatar source type.")
    preset_id: Optional[str] = Field(default=None, description="Preset avatar id when avatar_type=preset.")
    fps: Optional[int] = Field(default=25, ge=1, le=60, description="Output video fps.")
    resize_factor: Optional[float] = Field(default=1.0, ge=0.1, le=4.0, description="Down/up scale of output frames.")

    def has_audio_ref(self) -> bool:
        return bool(self.music_id or self.slice_id)


class GenerationResponse(BaseModel):
    task_id: str
    status: TaskState
    message: Optional[str] = None
    websocket_url: Optional[str] = None
    request_id: Optional[str] = None


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskState
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    stage: str = "-"
    message: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = 0.0
    updated_at: float = 0.0
    request_id: Optional[str] = None


class TaskListResponse(BaseModel):
    tasks: List[TaskStatusResponse]
    count: int
    limit: int


class ProgressEvent(BaseModel):
    task_id: str
    stage: str
    percent: float = Field(default=0.0, ge=0.0, le=100.0)
    message: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: float = 0.0


class GenerationErrorPayload(BaseModel):
    error: str
    message: str
    request_id: Optional[str] = None
    task_id: Optional[str] = None
