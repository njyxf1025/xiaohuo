from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from app.core.config import settings
from app.core.gpu import GPUManager
from app.core.logger import setup_logger

logger = setup_logger("sdh.wav2lip")

STEP_PREPROCESSING = "preprocessing"
STEP_EXTRACTING_FEATURES = "extracting_features"
STEP_GENERATING_LIP = "generating_lip"
STEP_COMPOSITING = "compositing"


class Wav2LipModel:
    def __init__(self, model_path: str | None = None) -> None:
        self._model_path = model_path or str(settings.MODELS_DIR / "wav2lip.pth")
        self._model = None
        self._device = None
        self._loaded = False
        logger.info(f"Wav2LipModel 初始化, 模型路径: {self._model_path}")

    def load_model(self) -> None:
        gpu_manager = GPUManager.get_instance()
        device_info = gpu_manager.get_device_info()
        device_type = device_info.get("device_type", "cpu")

        if device_type == "rocm":
            os.environ.setdefault("HSA_OVERRIDE_GFX_VERSION", "10.3.0")
            logger.info(
                "检测到 ROCm 设备, 已设置 HSA_OVERRIDE_GFX_VERSION=10.3.0"
            )

        self._device = gpu_manager.get_device()
        start_time = time.time()

        try:
            import torch

            if not Path(self._model_path).exists():
                logger.warning(
                    f"模型权重文件不存在: {self._model_path}, 跳过权重加载"
                )
                self._model = None
                self._loaded = False
                return

            state_dict = torch.load(
                self._model_path,
                map_location=self._device or "cpu",
                weights_only=True,
            )
            self._model = state_dict
            self._loaded = True
        except ImportError:
            logger.warning("torch 不可用, 模型加载降级为 CPU 模式")
            self._device = None
            self._loaded = False
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            self._loaded = False

        elapsed = time.time() - start_time
        logger.info(
            f"模型加载完成: path={self._model_path}, "
            f"device={self._device}, "
            f"耗时={elapsed:.2f}s, "
            f"loaded={self._loaded}"
        )

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
            logger.info("模型未加载, 自动加载中...")
            self.load_model()

        face_path = Path(face_image_path)
        audio_p = Path(audio_path)
        output_p = Path(output_path)

        if not face_path.exists():
            raise FileNotFoundError(f"人脸图片不存在: {face_image_path}")
        if not audio_p.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        wav2lip_dir = settings.MODELS_DIR / "Wav2Lip"
        inference_script = wav2lip_dir / "inference.py"

        if not inference_script.exists():
            raise FileNotFoundError(
                f"Wav2Lip 推理脚本不存在: {inference_script}, "
                f"请先克隆 Wav2Lip 仓库到 {wav2lip_dir}"
            )

        gpu_manager = GPUManager.get_instance()
        device_info = gpu_manager.get_device_info()
        device_type = device_info.get("device_type", "cpu")

        if device_type == "rocm":
            os.environ.setdefault("HSA_OVERRIDE_GFX_VERSION", "10.3.0")
            logger.info(
                "generate: 检测到 ROCm 设备, 已设置 HSA_OVERRIDE_GFX_VERSION=10.3.0"
            )

        device = gpu_manager.get_device()
        logger.info(
            f"开始 Wav2Lip 推理: face={face_image_path}, "
            f"audio={audio_path}, output={output_path}, device={device}"
        )

        output_p.parent.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback(STEP_PREPROCESSING, 0.0)

        env = os.environ.copy()
        if device_type == "rocm":
            env["HSA_OVERRIDE_GFX_VERSION"] = "10.3.0"

        cmd = [
            "python",
            str(inference_script),
            "--checkpoint_path",
            self._model_path,
            "--face",
            str(face_path),
            "--audio",
            str(audio_p),
            "--outfile",
            str(output_p),
        ]

        if device is not None and device_type != "cpu":
            cmd.extend(["--device", str(device)])

        if progress_callback:
            progress_callback(STEP_PREPROCESSING, 0.2)

        start_time = time.time()

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        if progress_callback:
            progress_callback(STEP_EXTRACTING_FEATURES, 0.2)

        steps = [
            (STEP_EXTRACTING_FEATURES, 0.2, 0.4, 5),
            (STEP_GENERATING_LIP, 0.4, 0.8, 10),
            (STEP_COMPOSITING, 0.8, 1.0, 5),
        ]

        for step_name, start_progress, end_progress, num_ticks in steps:
            for i in range(num_ticks):
                if process.poll() is not None:
                    break
                progress = start_progress + (end_progress - start_progress) * (
                    (i + 1) / num_ticks
                )
                if progress_callback:
                    progress_callback(step_name, round(progress, 4))
                time.sleep(0.5)

        stdout, stderr = process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode(errors="replace").strip()
            logger.error(f"Wav2Lip 推理失败: returncode={process.returncode}, error={error_msg}")
            raise RuntimeError(f"Wav2Lip 推理失败: {error_msg}")

        if not output_p.exists():
            raise FileNotFoundError(f"推理完成但输出文件不存在: {output_path}")

        elapsed = time.time() - start_time
        logger.info(
            f"Wav2Lip 推理完成: output={output_path}, 耗时={elapsed:.2f}s"
        )

        if progress_callback:
            progress_callback(STEP_COMPOSITING, 1.0)

        return str(output_p)
