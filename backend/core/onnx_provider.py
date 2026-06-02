from __future__ import annotations

import os
from typing import List, Tuple

from .logging import get_logger

_logger = get_logger("core.onnx_provider")

ProviderList = List[str]


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


def select_providers() -> Tuple[ProviderList, str]:
    if not _ort_available():
        return (["CPUExecutionProvider"], "cpu-fallback")

    try:
        providers = _ort_get_providers()
        has_cpu = "CPUExecutionProvider" in providers

        dml_module_ok = _directml_module_ok()
        dml_in_list = "DmlExecutionProvider" in providers
        dml_devices = _dml_device_count() if dml_module_ok or dml_in_list else 0

        if dml_in_list and dml_devices > 0:
            providers_list: ProviderList = ["DmlExecutionProvider", "CPUExecutionProvider"] if has_cpu else ["DmlExecutionProvider"]
            _logger.info(
                "ONNX provider chosen=%s dml_devices=%d providers=%s",
                "dml",
                dml_devices,
                providers_list,
            )
            return (providers_list, "dml")

        if dml_in_list and dml_devices == 0:
            if has_cpu:
                _logger.warning(
                    "DmlExecutionProvider listed but no DML devices available; falling back to CPUExecutionProvider",
                )
                return (["CPUExecutionProvider"], "cpu-fallback")
            return (["DmlExecutionProvider"], "dml-no-device")

        if has_cpu:
            _logger.warning("DmlExecutionProvider unavailable; falling back to CPUExecutionProvider")
            return (["CPUExecutionProvider"], "cpu-fallback")

        return (providers or ["CPUExecutionProvider"], "cpu-fallback")
    except Exception as exc:
        _logger.exception("provider selection failed: %s", exc)
        return (["CPUExecutionProvider"], "cpu-fallback")


def get_device_id_for_provider(label: str, providers: ProviderList) -> int:
    if label == "dml":
        try:
            return int(os.getenv("DML_DEVICE_ID", "0"))
        except Exception:
            return 0
    return 0
