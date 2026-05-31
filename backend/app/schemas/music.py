from __future__ import annotations

from pydantic import BaseModel, Field


class MusicUploadResponse(BaseModel):
    file_id: str
    filename: str
    duration: float
    format: str
    sample_rate: int
    channels: int
    chorus: ChorusInfoResponse | None = None


class ChorusInfoResponse(BaseModel):
    start_time: float
    end_time: float
    duration: float


class TrimRequest(BaseModel):
    file_id: str
    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)


class TrimResponse(BaseModel):
    file_id: str
    trimmed_file_path: str
    start_time: float
    end_time: float


class WaveformResponse(BaseModel):
    file_id: str
    waveform: list[float]
    sample_rate: int
    duration: float
    chorus: ChorusInfoResponse | None = None
