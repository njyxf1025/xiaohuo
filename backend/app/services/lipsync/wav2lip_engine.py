from __future__ import annotations

import time
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.gpu import GPUManager
from app.core.logger import setup_logger
from app.services.lipsync.wav2lip_model import Wav2LipModel

logger = setup_logger("sdh.wav2lip_engine")


class Wav2LipEngine:
    def __init__(self) -> None:
        self._model = Wav2LipModel()
        logger.info("Wav2LipEngine 初始化完成")

    def process(
        self,
        face_image_path: str,
        audio_path: str,
        output_dir: str,
        progress_callback=None,
    ) -> dict:
        start_time = time.time()

        try:
            output_dir_path = Path(output_dir)
            output_dir_path.mkdir(parents=True, exist_ok=True)

            output_filename = f"lip_sync_{uuid.uuid4().hex[:8]}.mp4"
            output_path = str(output_dir_path / output_filename)

            result_path = self._model.generate(
                face_image_path=face_image_path,
                audio_path=audio_path,
                output_path=output_path,
                progress_callback=progress_callback,
            )

            elapsed = time.time() - start_time
            logger.info(f"唇形同步处理完成: output={result_path}, 耗时={elapsed:.2f}s")

            return {
                "success": True,
                "output_path": result_path,
                "duration": round(elapsed, 3),
                "error": None,
            }
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"唇形同步处理失败: {e}")
            return {
                "success": False,
                "output_path": "",
                "duration": round(elapsed, 3),
                "error": str(e),
            }

    def get_model_info(self) -> dict:
        gpu_manager = GPUManager.get_instance()
        device_info = gpu_manager.get_device_info()

        return {
            "name": "Wav2Lip",
            "version": "1.0",
            "loaded": self._model.is_loaded(),
            "device": str(device_info.get("device_type", "cpu")),
        }
