from __future__ import annotations

"""ONNX execution provider selection — DirectML‑only, zero CPU fallback.

Every ONNX InferenceSession created by this project MUST use the
providers list returned by :func:`select_providers`.  That list
contains ONLY ``["DmlExecutionProvider"]``.
``CPUExecutionProvider`` is intentionally absent — DirectML is
required for every model (Wav2Lip, face detection, vocal separation,
resemble denoiser).  If DirectML is not available the system refuses
to start and returns a ``degraded`` status; the frontend renders an
amber degradation card instead of trying to run inference on CPU.

DirectML constraint: parallel graph execution is NOT supported.
Every session MUST set ``ORT_SEQUENTIAL``:

    session_options = ort.SessionOptions()
    session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session = ort.InferenceSession(
        model_path, session_options, providers=["DmlExecutionProvider"]
    )

The helper :func:`select_providers` handles the full probe:
  1. ``onnxruntime`` importable?
  2. ``onnxruntime-directml`` importable?
  3. ``DmlExecutionProvider`` registered?
  4. DirectML‑capable GPU detected?

If any check fails it raises :class:`DirectMLNotAvailable` (which
callers MUST NOT catch-and-fallback — the only allowed response is to
abort and report the reason).
"""

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
    """Select ONNX execution providers — DirectML only, no CPU fallback.

    Returns
    -------
    Tuple[ProviderList, str]
        * ``providers`` — always ``["DmlExecutionProvider"]`` (never
          contains ``"CPUExecutionProvider"``).
        * ``label`` — short human-readable label (``"dml"``).

    Raises
    ------
    DirectMLNotAvailable
        If any of the four prerequisites are not met.
    """
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


def build_directml_session_options(ort=None) -> object:
    """Return a pre-configured ``ort.SessionOptions`` for DirectML.

    Sets ``ORT_SEQUENTIAL`` (required — DirectML does not support
    parallel graph execution) and reasonable defaults.

    Parameters
    ----------
    ort : module, optional
        The ``onnxruntime`` module.  If ``None`` it will be imported.
    """
    if ort is None:
        import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    # Memory-efficient: single-threaded inter-op parallelism
    try:
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
    except Exception:
        pass
    # Disable graph optimizations that may conflict with DirectML
    try:
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
    except Exception:
        pass
    return opts


def create_directml_session(
    model_path: str,
    ort=None,
    session_options=None,
) -> object:
    """Create an ``ort.InferenceSession`` with DirectML only.

    This is the canonical factory for every ONNX session in the
    project.  It calls :func:`select_providers` internally, so the
    returned session is guaranteed to use ``DmlExecutionProvider``
    (never CPU).

    Parameters
    ----------
    model_path : str
        Path to the ONNX model file.
    ort : module, optional
    session_options : ort.SessionOptions, optional
        If ``None``, :func:`build_directml_session_options` is used.

    Returns
    -------
    ort.InferenceSession
    """
    if ort is None:
        import onnxruntime as ort
    providers, _label = select_providers()
    if session_options is None:
        session_options = build_directml_session_options(ort)
    try:
        return ort.InferenceSession(
            model_path,
            sess_options=session_options,
            providers=providers,
        )
    except TypeError:
        return ort.InferenceSession(model_path, providers=providers)


def get_device_id_for_provider(label: str, providers: ProviderList) -> int:
    if label == "dml":
        try:
            return int(os.getenv("DML_DEVICE_ID", "0"))
        except Exception:
            return 0
    return 0
