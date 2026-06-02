from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ChorusSegment(BaseModel):
    start_sec: float = Field(..., ge=0.0)
    end_sec: float = Field(..., ge=0.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = Field(default="pychorus")


class MusicMetadata(BaseModel):
    music_id: str
    filename: str
    extension: str
    size_bytes: int
    mime_type: Optional[str] = None
    duration_sec: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    status: str = "ready"
    chorus: Optional[ChorusSegment] = None
    created_at: float = 0.0


class MusicUploadResponse(BaseModel):
    music_id: str
    filename: str
    duration_sec: float
    sample_rate: int
    channels: int
    chorus: Optional[ChorusSegment] = None
    status: str


class MusicMetadataResponse(MusicMetadata):
    pass


class ChorusDetectResponse(BaseModel):
    music_id: str
    chorus: Optional[ChorusSegment] = None
    status: str


class AudioSliceResponse(BaseModel):
    slice_id: str
    music_id: str
    start_sec: float
    end_sec: float
    file_path: str
    download_url: str
    duration_sec: float


class WaveformResponse(BaseModel):
    music_id: str
    duration_sec: float
    sample_rate: int
    channels: int
    peaks: List[float]
    num_peaks: int
    num_samples: int


class AudioSliceRequest(BaseModel):
    start_sec: float = Field(..., ge=0.0)
    end_sec: float = Field(..., gt=0.0)
    format: Optional[str] = None


class ErrorPayload(BaseModel):
    error: str
    message: str
    request_id: Optional[str] = None
