from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from app.core.config import settings
from app.core.gpu import GPUManager
from app.core.logger import setup_logger

logger = setup_logger("sdh.sadtalker")


class SadTalkerModel:
    def __init__(self, model_path: str | None = None) -> None:
        self._model_path = model_path or str(settings.MODELS_DIR / "sadtalker")
        self._loaded = False
        self._device = None
        logger.info(f"SadTalkerModel 初始化, 模型路径: {self._model_path}")

    def load_model(self) -> None:
        gpu_manager = GPUManager.get_instance()
        self._device = gpu_manager.get_device()
        logger.info(f"SadTalker 使用设备: {self._device}")

        memory_info = gpu_manager.get_memory_info()
        if memory_info is not None:
            total_gb = memory_info["total"] / (1024 ** 3)
            available_gb = memory_info["available"] / (1024 ** 3)
            logger.info(
                f"GPU 内存: 总量={total_gb:.2f}GB, "
                f"可用={available_gb:.2f}GB"
            )

        model_dir = Path(self._model_path)
        if not model_dir.exists():
            logger.warning(f"模型目录不存在: {self._model_path}, 将在推理时按需加载")

        self._loaded = True
        logger.info("SadTalker 模型加载完成")

    def is_loaded(self) -> bool:
        return self._loaded

    def generate(
        self,
        face_image_path: str,
        audio_path: str,
        output_path: str,
        progress_callback=None,
    ) -> str:
        if not self._loaded:
            self.load_model()

        model_dir = Path(self._model_path)
        inference_script = model_dir / "inference.py"
        if not inference_script.exists():
            raise FileNotFoundError(
                f"SadTalker 推理脚本不存在: {inference_script}. "
                f"请确保 models/sadtalker/ 目录包含 SadTalker 仓库代码"
            )

        face_path = Path(face_image_path)
        if not face_path.exists():
            raise FileNotFoundError(f"人脸图片不存在: {face_image_path}")

        audio = Path(audio_path)
        if not audio.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "python",
            str(inference_script),
            "--face_image_path",
            str(face_image_path),
            "--audio_path",
            str(audio_path),
            "--output_path",
            str(output_path),
        ]

        logger.info(f"SadTalker 推理开始: {' '.join(cmd)}")

        start_time = time.time()

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(model_dir),
        )

        for line in process.stdout:
            line = line.strip()
            if line:
                logger.info(f"[SadTalker] {line}")
                if progress_callback is not None:
                    try:
                        progress_callback(line)
                    except Exception:
                        pass

        return_code = process.wait()
        duration = time.time() - start_time

        if return_code != 0:
            raise RuntimeError(
                f"SadTalker 推理失败, 返回码: {return_code}, "
                f"耗时: {duration:.2f}s"
            )

        if not output.exists():
            raise RuntimeError(
                f"SadTalker 推理完成但输出文件不存在: {output_path}"
            )

        logger.info(
            f"SadTalker 推理完成, 输出: {output_path}, 耗时: {duration:.2f}s"
        )

        return str(output_path)
