from __future__ import annotations

import os
from typing import List, Tuple

from .logging import get_logger

_logger = get_logger("core.onnx_provider")

ProviderList = List[str]


class DirectMLNotAvailable(RuntimeError):
    code = "directml_unavailable"

    def __init__(
        self,
        message: str = "DirectML execution provider is not available; CPU fallback is disabled",
    ) -> None:
        super().__init__(message)
        self.code = "directml_unavailable"


def _ort_available() -> bool:
    try:
        import onnxruntime  # type: ignore[import-not-found]

        return True
    except Exception as exc:
        _logger.warning("onnxruntime not importable: %s", exc)
        return False


def _ort_get_providers() -> ProviderList:
    try:
        import onnxruntime as ort  # type: ignore[import-not-found]

        return list(ort.get_available_providers())
    except Exception as exc:
        _logger.warning("onnxruntime.get_available_providers() failed: %s", exc)
        return []


def _dml_device_count() -> int:
    if os.getenv("FAKE_DML_DEVICES") is not None:
        try:
            return max(0, int(os.getenv("FAKE_DML_DEVICES", "0")))
        except Exception:
            return 0
    try:
        import onnxruntime as ort  # type: ignore[import-not-found]

        capi = getattr(ort, "capi", None)
        if capi is None:
            return 0
        pybind = getattr(capi, "_pybind_state", None)
        if pybind is None:
            return 0
        get_ex = getattr(pybind, "get_available_providers_ex", None)
        if get_ex is None:
            return 0
        providers_ex = get_ex()
        dml_devices = []
        for p in providers_ex:
            short = getattr(p, "short_name", None) or getattr(p, "name", "")
            if isinstance(short, bytes):
                short = short.decode("utf-8", errors="ignore")
            if not short and isinstance(p, (tuple, list)) and p:
                short = p[0]
            if isinstance(short, str) and "Dml" in short:
                device_id = getattr(p, "device_id", 0)
                dml_devices.append((short, device_id))
        return len(dml_devices)
    except Exception as exc:
        _logger.debug("get_available_providers_ex failed: %s", exc)
        return 0


def _directml_module_ok() -> bool:
    try:
        import importlib

        mod = importlib.import_module("onnxruntime-directml")
        _ = mod
        return True
    except Exception as exc:
        _logger.info("onnxruntime-directml not available: %s", exc)
        return False


def is_directml_available() -> Tuple[bool, str]:
    if not _ort_available():
        return (False, "onnxruntime package not importable")
    if not _directml_module_ok():
        return (False, "onnxruntime-directml package not installed")
    providers = _ort_get_providers()
    if "DmlExecutionProvider" not in providers:
        return (False, "DmlExecutionProvider not registered in onnxruntime")
    dml_devices = _dml_device_count()
    if dml_devices <= 0:
        return (False, "no DirectML-capable GPU device detected")
    return (True, f"DirectML ready: {dml_devices} device(s) detected")


def select_providers() -> Tuple[ProviderList, str]:
    ok, reason = is_directml_available()
    if not ok:
        _logger.error(
            "DirectML not available; refusing to fall back to CPU. reason=%s "
            "Install onnxruntime-directml and ensure a DirectML-capable GPU is present.",
            reason,
            extra={"stage": "onnx_provider.select", "reason": reason},
        )
        raise DirectMLNotAvailable(reason)
    providers_list: ProviderList = ["DmlExecutionProvider"]
    dml_devices = _dml_device_count()
    _logger.info(
        "ONNX provider chosen=DmlExecutionProvider dml_devices=%d (CPU fallback disabled)",
        dml_devices,
        extra={
            "stage": "onnx_provider.select",
            "providers": providers_list,
            "dml_devices": dml_devices,
        },
    )
    return (providers_list, "dml")


def get_device_id_for_provider(label: str, providers: ProviderList) -> int:
    if label == "dml":
        try:
            return int(os.getenv("DML_DEVICE_ID", "0"))
        except Exception:
            return 0
    return 0
