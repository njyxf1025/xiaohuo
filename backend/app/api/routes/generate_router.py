from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.logger import logger
from app.schemas.generation import (
    GenerateRequest,
    GenerateResponse,
    GenerationHistoryItem,
    GenerationHistoryResponse,
    TaskStatusResponse,
)
from app.services import avatar_service
from app.services.generation_service import model_scheduler, task_manager
from app.services.music_service import trim_audio

router = APIRouter(prefix="/api/generate", tags=["generate"])

VALID_MODELS = {"wav2lip", "sadtalker", "latentsync"}


def _resolve_music_file(file_id: str):
    from app.api.routes.music_router import _uploads_metadata

    meta = _uploads_metadata.get(file_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"音乐文件不存在: {file_id}")
    file_path = Path(meta["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"音乐文件已丢失: {file_id}")
    return file_path, meta


def _resolve_avatar(avatar_id: str) -> str:
    preset = avatar_service.get_preset_avatar(avatar_id)
    if preset:
        image_path = preset.get("image_path", "")
        if image_path and Path(image_path).exists():
            return image_path
        raise HTTPException(status_code=404, detail="预设形象文件不存在")

    custom = avatar_service.get_custom_avatar(avatar_id)
    if custom:
        file_path = custom.get("file_path", "")
        if file_path and Path(file_path).exists():
            return file_path
        raise HTTPException(status_code=404, detail="形象文件不存在")

    raise HTTPException(status_code=404, detail=f"形象不存在: {avatar_id}")


def _prepare_audio(file_id: str, meta: dict, start_time: float | None, end_time: float | None) -> str:
    source_path = meta["file_path"]

    if start_time is not None and end_time is not None:
        if start_time >= end_time:
            raise HTTPException(status_code=400, detail="start_time 必须小于 end_time")
        trimmed_dir = settings.DATA_DIR / "trimmed"
        trimmed_dir.mkdir(parents=True, exist_ok=True)
        trimmed_path = str(trimmed_dir / f"{file_id}_gen_trimmed.wav")
        trim_audio(source_path, start_time, end_time, trimmed_path)
        return trimmed_path

    if start_time is not None or end_time is not None:
        chorus = meta.get("chorus", {})
        if start_time is None:
            start_time = chorus.get("start_time", 0.0)
        if end_time is None:
            end_time = chorus.get("end_time", start_time + 30.0)
        if start_time >= end_time:
            raise HTTPException(status_code=400, detail="start_time 必须小于 end_time")
        trimmed_dir = settings.DATA_DIR / "trimmed"
        trimmed_dir.mkdir(parents=True, exist_ok=True)
        trimmed_path = str(trimmed_dir / f"{file_id}_gen_trimmed.wav")
        trim_audio(source_path, start_time, end_time, trimmed_path)
        return trimmed_path

    return source_path


@router.post("", response_model=GenerateResponse)
async def create_generation_task(req: GenerateRequest):
    if req.model not in VALID_MODELS:
        logger.warning(f"不支持的模型: {req.model}")
        raise HTTPException(
            status_code=400,
            detail=f"不支持的模型: {req.model}, 可选: {', '.join(sorted(VALID_MODELS))}",
        )

    music_file_path, music_meta = _resolve_music_file(req.music_file_id)

    face_image_path = _resolve_avatar(req.avatar_id)

    audio_path = _prepare_audio(req.music_file_id, music_meta, req.start_time, req.end_time)

    settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    params = {
        "model": req.model,
        "face_image_path": face_image_path,
        "audio_path": audio_path,
        "music_file_id": req.music_file_id,
        "avatar_id": req.avatar_id,
        "start_time": req.start_time,
        "end_time": req.end_time,
    }

    task_id = task_manager.create_task(params)

    asyncio.create_task(task_manager.run_task(task_id))

    logger.info(f"生成任务已提交: task_id={task_id}, model={req.model}")
    return GenerateResponse(task_id=task_id)


@router.get("/history", response_model=GenerationHistoryResponse)
async def get_generation_history():
    tasks = task_manager.get_all_tasks()
    items = []
    for task in tasks:
        params = task.get("params", {})
        items.append(
            GenerationHistoryItem(
                task_id=task["task_id"],
                status=task["status"],
                progress=task["progress"],
                current_step=task["current_step"],
                model=params.get("model", ""),
                music_file_id=params.get("music_file_id", ""),
                avatar_id=params.get("avatar_id", ""),
                result=task.get("result"),
                error=task.get("error"),
            )
        )
    return GenerationHistoryResponse(tasks=items, total=len(items))


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return TaskStatusResponse(
        task_id=task["task_id"],
        status=task["status"],
        progress=task["progress"],
        current_step=task["current_step"],
        result=task.get("result"),
        error=task.get("error"),
    )


@router.get("/{task_id}/result")
async def get_task_result(task_id: str):
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"任务尚未完成, 当前状态: {task['status']}")
    result = task.get("result", {})
    output_path = result.get("output_path", "")
    filename = Path(output_path).name if output_path else ""
    return {
        "task_id": task_id,
        "status": task["status"],
        "output_path": output_path,
        "filename": filename,
        "duration": result.get("duration"),
        "download_url": f"/api/generate/{task_id}/download",
    }


@router.get("/{task_id}/download")
async def download_task_result(task_id: str):
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"任务尚未完成, 当前状态: {task['status']}")
    result = task.get("result", {})
    output_path = result.get("output_path", "")
    if not output_path:
        raise HTTPException(status_code=404, detail="生成结果文件路径为空")
    file_path = Path(output_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="生成结果文件不存在")
    return FileResponse(
        path=str(file_path),
        media_type="video/mp4",
        filename=file_path.name,
    )
