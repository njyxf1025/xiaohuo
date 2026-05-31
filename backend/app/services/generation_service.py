from __future__ import annotations

import asyncio
import uuid
from typing import Any, Callable

from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger("sdh.generation")

_ENGINE_CLASSES = {
    "wav2lip": "app.services.lipsync.wav2lip_engine.Wav2LipEngine",
    "sadtalker": "app.services.lipsync.sadtalker_engine.SadTalkerEngine",
    "latentsync": "app.services.lipsync.latentsync_engine.LatentSyncEngine",
}


def _import_class(dotted_path: str) -> type:
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class ModelScheduler:
    def __init__(self) -> None:
        self._engines: dict[str, Any] = {}
        self._loaded: set[str] = set()
        logger.info("ModelScheduler 初始化完成 (惰性加载模式)")

    def get_engine(self, model_name: str) -> Any:
        if model_name not in _ENGINE_CLASSES:
            raise ValueError(f"不支持的模型: {model_name}, 可选: {list(_ENGINE_CLASSES.keys())}")
        if model_name not in self._engines:
            cls = _import_class(_ENGINE_CLASSES[model_name])
            self._engines[model_name] = cls()
            self._loaded.add(model_name)
            logger.info(f"引擎惰性加载: {model_name}")
        return self._engines[model_name]

    def is_engine_loaded(self, model_name: str) -> bool:
        return model_name in self._loaded

    def get_available_models(self) -> list[dict]:
        result = []
        for name in _ENGINE_CLASSES:
            if name in self._engines:
                result.append(self._engines[name].get_model_info())
            else:
                result.append({"name": name, "loaded": False})
        return result

    def generate_video(
        self,
        model_name: str,
        face_image_path: str,
        audio_path: str,
        output_dir: str,
        progress_callback: Callable | None = None,
    ) -> dict:
        engine = self.get_engine(model_name)
        logger.info(
            f"开始生成视频: model={model_name}, "
            f"face={face_image_path}, audio={audio_path}"
        )
        result = engine.process(
            face_image_path=face_image_path,
            audio_path=audio_path,
            output_dir=output_dir,
            progress_callback=progress_callback,
        )
        logger.info(
            f"视频生成完成: model={model_name}, "
            f"success={result.get('success')}, "
            f"duration={result.get('duration')}"
        )
        return result


class TaskManager:
    def __init__(self, scheduler: ModelScheduler) -> None:
        self._scheduler = scheduler
        self._tasks: dict[str, dict] = {}

    def create_task(self, params: dict) -> str:
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "progress": 0.0,
            "current_step": "初始化",
            "result": None,
            "error": None,
            "params": params,
        }
        logger.info(f"任务创建: task_id={task_id}")
        return task_id

    def update_task(
        self,
        task_id: str,
        status: str,
        progress: float,
        step: str,
        result: dict | None = None,
        error: str | None = None,
    ) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            logger.warning(f"任务不存在: task_id={task_id}")
            return
        task["status"] = status
        task["progress"] = progress
        task["current_step"] = step
        if result is not None:
            task["result"] = result
        if error is not None:
            task["error"] = error
        if status in ("completed", "failed"):
            logger.info(
                f"任务更新: task_id={task_id}, status={status}, "
                f"progress={progress}, step={step}"
            )
        else:
            logger.debug(
                f"任务更新: task_id={task_id}, status={status}, "
                f"progress={progress}, step={step}"
            )

    def get_task(self, task_id: str) -> dict | None:
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[dict]:
        return list(self._tasks.values())

    async def run_task(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return

        params = task["params"]
        model_name = params.get("model", "wav2lip")
        face_image_path = params.get("face_image_path", "")
        audio_path = params.get("audio_path", "")
        output_dir = str(settings.OUTPUT_DIR)

        logger.info(
            f"任务开始执行: task_id={task_id}, model={model_name}, "
            f"face={face_image_path}, audio={audio_path}"
        )
        self.update_task(task_id, "processing", 0.0, "准备生成")

        def progress_callback(progress: float):
            self.update_task(task_id, "processing", progress, "处理中")

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._scheduler.generate_video,
                model_name,
                face_image_path,
                audio_path,
                output_dir,
                progress_callback,
            )

            if result.get("success"):
                self.update_task(
                    task_id,
                    "completed",
                    100.0,
                    "生成完成",
                    result=result,
                )
                logger.info(
                    f"任务完成: task_id={task_id}, "
                    f"output={result.get('output_path')}, "
                    f"duration={result.get('duration')}"
                )
            else:
                self.update_task(
                    task_id,
                    "failed",
                    task["progress"],
                    "生成失败",
                    error=result.get("error", "未知错误"),
                )
                logger.error(
                    f"任务失败: task_id={task_id}, "
                    f"error={result.get('error', '未知错误')}"
                )
        except Exception as e:
            logger.error(f"任务执行异常: task_id={task_id}, error={e}", exc_info=True)
            self.update_task(
                task_id,
                "failed",
                task["progress"],
                "执行异常",
                error=str(e),
            )


model_scheduler = ModelScheduler()
task_manager = TaskManager(model_scheduler)
