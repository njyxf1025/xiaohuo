from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File

from app.core.config import settings
from app.core.logger import logger
from app.schemas.music import (
    ChorusInfoResponse,
    MusicUploadResponse,
    TrimRequest,
    TrimResponse,
    WaveformResponse,
)
from app.services.music_service import detect_chorus, get_audio_info, get_waveform, trim_audio

router = APIRouter(prefix="/api/music", tags=["music"])

ALLOWED_EXTENSIONS = {"mp3", "wav", "m4a", "flac"}
MAX_FILE_SIZE = 50 * 1024 * 1024

_uploads_metadata: dict[str, dict] = {}


def _get_upload_dir() -> Path:
    upload_dir = settings.UPLOAD_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _find_file_by_id(file_id: str) -> Path:
    meta = _uploads_metadata.get(file_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_id}")
    file_path = Path(meta["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件已丢失: {file_id}")
    return file_path


@router.post("/upload", response_model=MusicUploadResponse)
async def upload_music(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    ext = Path(file.filename).suffix.lstrip(".").lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}, 仅支持 {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过50MB限制")

    file_id = str(uuid.uuid4())
    upload_dir = _get_upload_dir()
    save_path = upload_dir / f"{file_id}.{ext}"

    save_path.write_bytes(content)
    logger.info(f"文件已保存: {save_path}")

    try:
        audio_info = get_audio_info(str(save_path))
    except Exception as e:
        save_path.unlink(missing_ok=True)
        logger.error(f"获取音频信息失败: {e}")
        raise HTTPException(status_code=400, detail=f"无法解析音频文件: {e}")

    chorus_data = detect_chorus(str(save_path))
    chorus_info = ChorusInfoResponse(**chorus_data) if chorus_data else None

    _uploads_metadata[file_id] = {
        "file_path": str(save_path),
        "filename": file.filename,
        "chorus": chorus_data,
        **audio_info,
    }

    return MusicUploadResponse(
        file_id=file_id,
        filename=file.filename,
        duration=audio_info["duration"],
        format=audio_info["format"],
        sample_rate=audio_info["sample_rate"],
        channels=audio_info["channels"],
        chorus=chorus_info,
    )


@router.post("/trim", response_model=TrimResponse)
async def trim_music(req: TrimRequest):
    file_path = _find_file_by_id(req.file_id)

    if req.start_time >= req.end_time:
        raise HTTPException(status_code=400, detail="start_time 必须小于 end_time")

    output_dir = settings.DATA_DIR / "trimmed"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{req.file_id}_trimmed.wav"

    try:
        trim_audio(str(file_path), req.start_time, req.end_time, str(output_path))
    except Exception as e:
        logger.error(f"音频截取失败: {e}")
        raise HTTPException(status_code=500, detail=f"音频截取失败: {e}")

    return TrimResponse(
        file_id=req.file_id,
        trimmed_file_path=str(output_path),
        start_time=req.start_time,
        end_time=req.end_time,
    )


@router.get("/waveform/{file_id}", response_model=WaveformResponse)
async def get_waveform_data(file_id: str):
    file_path = _find_file_by_id(file_id)
    meta = _uploads_metadata[file_id]

    try:
        waveform = get_waveform(str(file_path))
    except Exception as e:
        logger.error(f"波形数据生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"波形数据生成失败: {e}")

    chorus_data = meta.get("chorus")
    chorus_info = ChorusInfoResponse(**chorus_data) if chorus_data else None

    return WaveformResponse(
        file_id=file_id,
        waveform=waveform,
        sample_rate=meta["sample_rate"],
        duration=meta["duration"],
        chorus=chorus_info,
    )
