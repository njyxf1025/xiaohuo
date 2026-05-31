from __future__ import annotations

from typing import Any

from app.core.logger import setup_logger

logger = setup_logger("sdh")


def detect_gpu() -> dict[str, Any]:
    try:
        import torch

        torch_version = torch.__version__

        if not torch.cuda.is_available():
            logger.info("未检测到可用 GPU，使用 CPU 模式")
            return {
                "device_type": "cpu",
                "device_name": "CPU",
                "device_index": None,
                "torch_version": torch_version,
                "backend_version": None,
            }

        device_index = torch.cuda.current_device()
        device_name = torch.cuda.get_device_name(device_index)

        if getattr(torch.version, "hip", None) is not None:
            device_type = "rocm"
            backend_version = torch.version.hip
        elif getattr(torch.version, "cuda", None) is not None:
            device_type = "cuda"
            backend_version = torch.version.cuda
        else:
            device_type = "cuda"
            backend_version = None

        logger.info(
            f"检测到 GPU: device_type={device_type}, "
            f"device_name={device_name}, "
            f"backend_version={backend_version}"
        )

        return {
            "device_type": device_type,
            "device_name": device_name,
            "device_index": device_index,
            "torch_version": torch_version,
            "backend_version": backend_version,
        }
    except ImportError:
        logger.info("torch 不可用，使用 CPU 模式")
        return {
            "device_type": "cpu",
            "device_name": "CPU",
            "device_index": None,
            "torch_version": None,
            "backend_version": None,
        }


class GPUManager:
    _instance: GPUManager | None = None

    def __init__(self) -> None:
        self._device_info = detect_gpu()
        logger.info(
            f"GPUManager 初始化完成: "
            f"device_type={self._device_info['device_type']}, "
            f"device_name={self._device_info['device_name']}, "
            f"torch_version={self._device_info['torch_version']}, "
            f"backend_version={self._device_info['backend_version']}"
        )

    @classmethod
    def get_instance(cls) -> GPUManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_device(self):
        try:
            import torch

            if self._device_info["device_type"] == "cpu":
                return torch.device("cpu")
            return torch.device(
                "cuda",
                self._device_info["device_index"] or 0,
            )
        except ImportError:
            return None

    def get_device_info(self) -> dict[str, Any]:
        return dict(self._device_info)

    def get_memory_info(self) -> dict[str, Any] | None:
        if self._device_info["device_type"] == "cpu":
            return None

        try:
            import torch

            device = self.get_device()
            if device is None:
                return None

            total = torch.cuda.get_device_properties(device).total_memory
            allocated = torch.cuda.memory_allocated(device)
            available = total - allocated

            logger.debug(
                f"GPU 内存: 已用={allocated / (1024 ** 3):.2f}GB, "
                f"总量={total / (1024 ** 3):.2f}GB, "
                f"可用={available / (1024 ** 3):.2f}GB"
            )

            return {
                "total": total,
                "allocated": allocated,
                "available": available,
            }
        except ImportError:
            return None

    def is_available(self) -> bool:
        return self._device_info["device_type"] != "cpu"
