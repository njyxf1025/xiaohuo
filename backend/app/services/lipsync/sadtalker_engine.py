from __future__ import annotations

import time
import uuid
from pathlib import Path

from app.core.gpu import GPUManager
from app.core.logger import setup_logger
from app.services.lipsync.sadtalker_model import SadTalkerModel

logger = setup_logger("sdh.sadtalker_engine")


class SadTalkerEngine:
    def __init__(self) -> None:
        self._model = SadTalkerModel()
        logger.info("SadTalkerEngine 初始化")

    def process(
        self,
        face_image_path: str,
        audio_path: str,
        output_dir: str,
        progress_callback=None,
    ) -> dict:
        start_time = time.time()

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_filename = f"sadtalker_{uuid.uuid4().hex[:8]}.mp4"
        output_path = str(out_dir / output_filename)

        try:
            result_path = self._model.generate(
                face_image_path=face_image_path,
                audio_path=audio_path,
                output_path=output_path,
                progress_callback=progress_callback,
            )
            duration = time.time() - start_time
            logger.info(f"SadTalker 处理完成, 耗时: {duration:.2f}s")
            return {
                "success": True,
                "output_path": result_path,
                "duration": duration,
                "error": None,
            }
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"SadTalker 处理失败: {e}")
            return {
                "success": False,
                "output_path": "",
                "duration": duration,
                "error": str(e),
            }

    def get_model_info(self) -> dict:
        gpu_manager = GPUManager.get_instance()
        device_info = gpu_manager.get_device_info()
        memory_info = gpu_manager.get_memory_info()

        return {
            "name": "SadTalker",
            "type": "diffusion",
            "loaded": self._model.is_loaded(),
            "device": str(device_info.get("device_type", "unknown")),
            "gpu_memory": (
                {
                    "total_gb": round(memory_info["total"] / (1024 ** 3), 2),
                    "available_gb": round(memory_info["available"] / (1024 ** 3), 2),
                }
                if memory_info
                else None
            ),
        }
