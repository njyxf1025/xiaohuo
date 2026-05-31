from __future__ import annotations

import time
import uuid
from pathlib import Path

from app.core.gpu import GPUManager
from app.core.logger import setup_logger
from app.services.lipsync.latentsync_model import LatentSyncModel

logger = setup_logger("sdh.latentsync_engine")

LATENTSYNC_MIN_VRAM_GB = 8


class LatentSyncEngine:
    def __init__(self) -> None:
        self._model = LatentSyncModel()
        self._num_inference_steps: int = 20
        self._guidance_scale: float = 1.5
        logger.info(
            f"LatentSyncEngine 初始化, "
            f"num_inference_steps={self._num_inference_steps}, "
            f"guidance_scale={self._guidance_scale}"
        )

    @property
    def num_inference_steps(self) -> int:
        return self._num_inference_steps

    @num_inference_steps.setter
    def num_inference_steps(self, value: int) -> None:
        self._num_inference_steps = value

    @property
    def guidance_scale(self) -> float:
        return self._guidance_scale

    @guidance_scale.setter
    def guidance_scale(self, value: float) -> None:
        self._guidance_scale = value

    def _check_gpu_memory(self) -> None:
        gpu_manager = GPUManager.get_instance()
        memory_info = gpu_manager.get_memory_info()
        if memory_info is None:
            logger.warning("无法获取 GPU 内存信息, 跳过内存检查")
            return

        available_gb = memory_info["available"] / (1024 ** 3)
        if available_gb < LATENTSYNC_MIN_VRAM_GB:
            raise RuntimeError(
                f"LatentSync 至少需要 {LATENTSYNC_MIN_VRAM_GB}GB 可用 VRAM, "
                f"当前可用 {available_gb:.2f}GB"
            )
        logger.info(f"GPU 内存检查通过, 可用 VRAM: {available_gb:.2f}GB")

    def process(
        self,
        face_image_path: str,
        audio_path: str,
        output_dir: str,
        progress_callback=None,
    ) -> dict:
        start_time = time.time()

        try:
            self._check_gpu_memory()
        except RuntimeError as e:
            logger.error(f"GPU 内存不足: {e}")
            return {
                "success": False,
                "output_path": "",
                "duration": 0.0,
                "error": str(e),
            }

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_filename = f"latentsync_{uuid.uuid4().hex[:8]}.mp4"
        output_path = str(out_dir / output_filename)

        try:
            result_path = self._model.generate(
                face_image_path=face_image_path,
                audio_path=audio_path,
                output_path=output_path,
                progress_callback=progress_callback,
            )
            duration = time.time() - start_time
            logger.info(f"LatentSync 处理完成, 耗时: {duration:.2f}s")
            return {
                "success": True,
                "output_path": result_path,
                "duration": duration,
                "error": None,
            }
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"LatentSync 处理失败: {e}")
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
            "name": "LatentSync",
            "type": "diffusion",
            "loaded": self._model.is_loaded(),
            "num_inference_steps": self._num_inference_steps,
            "guidance_scale": self._guidance_scale,
            "min_vram_gb": LATENTSYNC_MIN_VRAM_GB,
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
