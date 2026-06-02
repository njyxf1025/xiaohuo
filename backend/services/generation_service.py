from __future__ import annotations

import asyncio
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import get_settings
from core.logging import get_logger
from core.request_id import get_request_id
from models.generation_schemas import GenerationRequest, TaskState
from services.avatar_service import AvatarService, get_avatar_service
from services.music_service import get_music_service
from services.task_manager import TaskCancelled, TaskManager, get_task_manager
from services.wav2lip_engine import (
    DEFAULT_FPS,
    DEFAULT_RESIZE_FACTOR,
    Wav2LipDirectMLNotAvailable,
)
from services.wav2lip_pipeline import PipelineRequest, run_pipeline
from utils import files as file_utils

_logger = get_logger("services.generation_service")

OUTPUTS_DIRNAME = "outputs"
MIN_DURATION_SEC = 0.2
MAX_DURATION_SEC = 60.0


@dataclass
class ResolvedSources:
    audio_path: Path
    avatar_path: Path
    avatar_kind: str
    slice_start: float
    slice_end: float
    music_id: Optional[str]
    avatar_id: Optional[str]
    preset_id: Optional[str]


class GenerationService:
    _instance: Optional["GenerationService"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._bg_tasks: Dict[str, asyncio.Task[Any]] = {}

    @classmethod
    def instance(cls) -> "GenerationService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @staticmethod
    def outputs_dir() -> Path:
        settings = get_settings()
        target = settings.resolved_data_dir() / OUTPUTS_DIRNAME
        target.mkdir(parents=True, exist_ok=True)
        return target

    @staticmethod
    def output_video_path(task_id: str) -> Path:
        return GenerationService.outputs_dir() / f"{task_id}.mp4"

    @staticmethod
    def output_thumbnail_path(task_id: str) -> Path:
        return GenerationService.outputs_dir() / f"{task_id}.jpg"

    def resolve_sources(
        self,
        req: GenerationRequest,
    ) -> ResolvedSources:
        music = get_music_service()
        avatars = get_avatar_service()
        slice_start: float = 0.0
        slice_end: float = 0.0
        music_id: Optional[str] = None
        audio_path: Optional[Path] = None
        if req.slice_id:
            slc = music.get_slice(req.slice_id)
            if slc is None:
                raise FileNotFoundError(f"audio slice not found: {req.slice_id}")
            audio_path = Path(slc.file_path)
            slice_start = float(slc.start_sec)
            slice_end = float(slc.end_sec)
            music_id = slc.music_id
        elif req.music_id:
            rec = music.get_music(req.music_id)
            if rec is None:
                raise FileNotFoundError(f"music not found: {req.music_id}")
            audio_path = Path(rec.file_path)
            music_id = rec.music_id
            s = req.start_sec if req.start_sec is not None else 0.0
            e = req.end_sec if req.end_sec is not None else float(rec.duration_sec)
            if e <= s:
                raise ValueError("end_sec must be greater than start_sec")
            slice_start = float(s)
            slice_end = float(e)
        else:
            raise ValueError("either music_id or slice_id is required")

        if audio_path is None or not audio_path.exists():
            raise FileNotFoundError(f"audio file missing on disk: {audio_path}")

        avatar_kind: Optional[str] = None
        avatar_path: Optional[Path] = None
        avatar_id: Optional[str] = req.avatar_id
        preset_id: Optional[str] = req.preset_id
        if req.avatar_type == "preset":
            if not preset_id:
                raise ValueError("preset_id is required when avatar_type='preset'")
            preset = avatars.get_preset(preset_id)
            if preset is None:
                raise FileNotFoundError(f"preset not found: {preset_id}")
            avatar_kind = "image"
            avatar_path = Path(preset.file_path)
        elif req.avatar_type == "image":
            if not avatar_id:
                raise ValueError("avatar_id is required when avatar_type='image'")
            rec = avatars.get_avatar(avatar_id)
            if rec is None:
                raise FileNotFoundError(f"avatar not found: {avatar_id}")
            avatar_kind = "image"
            avatar_path = Path(rec.file_path)
        elif req.avatar_type == "video":
            if not avatar_id:
                raise ValueError("avatar_id is required when avatar_type='video'")
            rec = avatars.get_avatar(avatar_id)
            if rec is None:
                raise FileNotFoundError(f"avatar not found: {avatar_id}")
            avatar_kind = "video"
            avatar_path = Path(rec.file_path)
        else:
            raise ValueError(f"unsupported avatar_type: {req.avatar_type}")

        if avatar_path is None or not avatar_path.exists():
            raise FileNotFoundError(f"avatar file missing on disk: {avatar_path}")

        duration = slice_end - slice_start
        if duration < MIN_DURATION_SEC:
            raise ValueError(
                f"audio duration too short: {duration:.2f}s (min {MIN_DURATION_SEC}s)"
            )
        if duration > MAX_DURATION_SEC:
            raise ValueError(
                f"audio duration too long: {duration:.2f}s (max {MAX_DURATION_SEC}s)"
            )

        return ResolvedSources(
            audio_path=audio_path,
            avatar_path=avatar_path,
            avatar_kind=avatar_kind,
            slice_start=slice_start,
            slice_end=slice_end,
            music_id=music_id,
            avatar_id=avatar_id,
            preset_id=preset_id,
        )

    def start_generation(
        self,
        params: GenerationRequest,
        request_id: Optional[str] = None,
    ) -> str:
        manager = get_task_manager()
        rid = request_id or get_request_id()
        params_dict = params.model_dump()
        task_id = manager.create_task(params=params_dict, request_id=rid)

        try:
            from services.wav2lip_engine import Wav2LipEngine
            engine = Wav2LipEngine.instance()
            dml_ok, dml_reason = engine.is_directml_ready()
            if not dml_ok:
                err = (
                    f"DirectML unavailable: {dml_reason}. "
                    "Install onnxruntime-directml and ensure a DirectML-capable GPU is present. "
                    "CPU fallback has been disabled because inference would be unusable."
                )
                _logger.error(
                    "refusing to start generation: DirectML unavailable",
                    extra={
                        "stage": "generation.start",
                        "task_id": task_id,
                        "reason": dml_reason,
                        "err_message": err,
                        "error_code": "directml_unavailable",
                    },
                )
                manager.fail_task(task_id, err)
                return task_id
        except Exception as exc:
            _logger.exception("DirectML probe failed at start_generation: %s", exc)
            manager.fail_task(task_id, f"DirectML probe failed: {exc}")
            return task_id

        try:
            resolved = self.resolve_sources(params)
        except Exception as exc:
            manager.fail_task(task_id, str(exc))
            return task_id

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is None:
            thread = threading.Thread(
                target=self._sync_run_generation,
                args=(task_id, params, resolved, rid),
                daemon=True,
            )
            thread.start()
            with self._lock:
                self._bg_tasks[task_id] = thread
        else:
            task = loop.create_task(
                self._async_run_generation(task_id, params, resolved, rid)
            )
            with self._lock:
                self._bg_tasks[task_id] = task
        return task_id

    async def _async_run_generation(
        self,
        task_id: str,
        params: GenerationRequest,
        resolved: ResolvedSources,
        request_id: Optional[str],
    ) -> None:
        try:
            await asyncio.to_thread(
                self._run_generation_blocking,
                task_id,
                params,
                resolved,
                request_id,
            )
        except Exception as exc:
            manager = get_task_manager()
            manager.fail_task(task_id, f"pipeline crashed: {exc}")
            _logger.exception("generation task crashed: %s", exc)

    def _sync_run_generation(
        self,
        task_id: str,
        params: GenerationRequest,
        resolved: ResolvedSources,
        request_id: Optional[str],
    ) -> None:
        try:
            self._run_generation_blocking(task_id, params, resolved, request_id)
        except Exception as exc:
            manager = get_task_manager()
            manager.fail_task(task_id, f"pipeline crashed: {exc}")
            _logger.exception("generation task crashed: %s", exc)

    def _run_generation_blocking(
        self,
        task_id: str,
        params: GenerationRequest,
        resolved: ResolvedSources,
        request_id: Optional[str],
    ) -> None:
        manager = get_task_manager()
        cb = manager.make_callback(task_id)
        try:
            cb("queued", 2.0, "task picked up")
        except TaskCancelled:
            return
        fps = int(params.fps or DEFAULT_FPS)
        resize = float(params.resize_factor or DEFAULT_RESIZE_FACTOR)
        output_path = self.output_video_path(task_id)
        thumb_path = self.output_thumbnail_path(task_id)
        req = PipelineRequest(
            audio_path=resolved.audio_path,
            avatar_path=resolved.avatar_path,
            avatar_kind=resolved.avatar_kind,
            slice_start=resolved.slice_start,
            slice_end=resolved.slice_end,
            output_path=output_path,
            thumbnail_path=thumb_path,
            fps=fps,
            resize_factor=resize,
            progress_cb=cb,
            preserve_audio=True,
        )
        try:
            result = run_pipeline(req)
        except Exception as exc:
            tb = traceback.format_exc(limit=4)
            err = f"{type(exc).__name__}: {exc}"
            _logger.error(
                "generation failed",
                extra={
                    "stage": "generation.run",
                    "task_id": task_id,
                    "err_message": err,
                    "trace": tb[-400:],
                },
            )
            manager.fail_task(task_id, err)
            return
        result_payload: Dict[str, Any] = {
            "output_path": str(result.output_path),
            "thumbnail_path": str(result.thumbnail_path) if result.thumbnail_path else None,
            "duration_sec": float(result.duration_sec),
            "num_frames": int(result.num_frames),
            "fps": int(result.fps),
            "width": int(result.width),
            "height": int(result.height),
            "mel_shape": list(result.mel_shape),
            "muxed": bool(result.muxed),
            "request_id": request_id,
        }
        manager.complete_task(task_id, result_payload)
        _logger.info(
            "generation completed",
            extra={
                "stage": "generation.complete",
                "task_id": task_id,
                "output": str(result.output_path),
                "num_frames": int(result.num_frames),
                "duration_sec": round(result.duration_sec, 3),
            },
        )

    def cancel(self, task_id: str) -> bool:
        manager = get_task_manager()
        return manager.cancel_task(task_id)

    def get_record(self, task_id: str) -> Optional[Dict[str, Any]]:
        manager = get_task_manager()
        rec = manager.get_task(task_id)
        if rec is None:
            return None
        return manager.to_response(rec)

    def list_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        manager = get_task_manager()
        return [manager.to_response(r) for r in manager.list_tasks(limit=limit)]


_service: Optional[GenerationService] = None
_service_lock = threading.Lock()


def get_generation_service() -> GenerationService:
    global _service
    with _service_lock:
        if _service is None:
            _service = GenerationService.instance()
        return _service
