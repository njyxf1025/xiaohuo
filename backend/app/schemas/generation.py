from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    music_file_id: str
    avatar_id: str
    model: str = "wav2lip"
    start_time: float | None = None
    end_time: float | None = None


class GenerateResponse(BaseModel):
    task_id: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: float = Field(ge=0, le=100)
    current_step: str
    result: dict | None = None
    error: str | None = None


class GenerationHistoryItem(BaseModel):
    task_id: str
    status: str
    progress: float
    current_step: str
    model: str
    music_file_id: str
    avatar_id: str
    result: dict | None = None
    error: str | None = None


class GenerationHistoryResponse(BaseModel):
    tasks: list[GenerationHistoryItem]
    total: int
