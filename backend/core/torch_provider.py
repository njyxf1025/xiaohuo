from __future__ import annotations

import os
from typing import Tuple

from .logging import get_logger

_logger = get_logger("core.torch_provider")


class TorchDirectMLNotAvailable(RuntimeError):
    code = "directml_unavailable"

    def __init__(
        self,
        message: str = (
            "torch-directml is not available; PyTorch-based engines (MuseTalk) cannot run. "
            "Install torch-directml and ensure a DirectML-capable GPU is present. "
            "CPU fallback is disabled because PyTorch CPU inference is unusable for real-time lip-sync."
        ),
    ) -> None:
        super().__init__(message)
        self.code = "directml_unavailable"


def _torch_directml_module_ok() -> bool:
    try:
        import importlib

        mod = importlib.import_module("torch_directml")
        _ = mod
        return True
    except Exception as exc:
        _logger.info("torch_directml not available: %s", exc)
        return False


def _torch_module_ok() -> bool:
    try:
        import importlib

        mod = importlib.import_module("torch")
        _ = mod
        return True
    except Exception as exc:
        _logger.info("torch not available: %s", exc)
        return False


def is_torch_directml_available() -> Tuple[bool, str]:
    if not _torch_module_ok():
        return (False, "torch package not importable")
    if not _torch_directml_module_ok():
        return (
            False,
            "torch-directml package not installed (pip install torch-directml)",
        )
    try:
        import torch_directml

        count = 0
        try:
            for _ in torch_directml.device_count():
                count += 1
        except Exception:
            try:
                count = int(torch_directml.device_count())
            except Exception:
                count = 1
        if count <= 0:
            return (False, "torch_directml reports zero devices")
        return (True, f"torch-directml ready: {count} device(s)")
    except Exception as exc:
        return (False, f"torch_directml probe failed: {exc}")


def get_torch_directml_device(device_id: int = 0):
    try:
        import torch_directml

        return torch_directml.device(int(device_id))
    except Exception as exc:
        raise TorchDirectMLNotAvailable(str(exc)) from exc
