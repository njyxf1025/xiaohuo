"""
Resemble Audio Denoiser — lightweight ONNX-based speech enhancement.

Wav2Lip-ONNX-HQ ships with a resemble audio denoiser that cleans up
vocals before they are fed into the lip-sync model.  Running it
*after* vocal separation (Spleeter / UVR5 / Mel-Band RoFormer) ensures
that the Wav2Lip model receives only clean, speech-like audio — the
mel-spectrogram it produces will be free of percussive rumble and
background hiss, which dramatically improves lip-sync accuracy.

The denoiser model file is expected at:

  <MODELS_DIR>/resemble_denoiser/resemble_denoiser.onnx

If the model file is not present the denoiser is a no-op (the
pipeline will log a warning and pass through the raw vocals).
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from core import onnx_provider
from core.config import get_settings
from core.logging import get_logger
from core.onnx_provider import DirectMLNotAvailable

_logger = get_logger("services.resemble_denoiser")

# ---------------------------------------------------------------------------
# Expected model file name
# ---------------------------------------------------------------------------
DENOISER_MODEL_NAME = "resemble_denoiser.onnx"

# ---------------------------------------------------------------------------
# Audio parameters — the denoiser expects 16 kHz mono
# ---------------------------------------------------------------------------
DENOISER_SAMPLE_RATE = 16000
DENOISER_CHUNK_SEC = 5.0       # process in 5-second chunks (low memory)
DENOISER_OVERLAP_SEC = 0.5     # cross-fade overlap


def _try_import_ort():
    try:
        import onnxruntime as ort
        return ort
    except Exception as exc:
        _logger.warning("onnxruntime import failed: %s", exc)
        return None


def _build_session_options(ort):
    try:
        session_options = ort.SessionOptions()
        session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        return session_options
    except Exception as exc:
        _logger.warning(
            "resemble_denoiser: failed to build sequential SessionOptions: %s", exc,
            extra={"stage": "resemble_denoiser.session_options"},
        )
        try:
            return ort.SessionOptions()
        except Exception as inner_exc:
            _logger.warning(
                "resemble_denoiser: ort.SessionOptions() unavailable: %s", inner_exc,
                extra={"stage": "resemble_denoiser.session_options"},
            )
            return None


def _create_inference_session(
    ort,
    model_path: str,
    providers: List[str],
    session_options,
):
    try:
        if session_options is not None:
            return ort.InferenceSession(
                model_path,
                sess_options=session_options,
                providers=providers,
            )
        return ort.InferenceSession(model_path, providers=providers)
    except TypeError:
        return ort.InferenceSession(model_path, providers=providers)


def _linear_crossfade(
    a: np.ndarray,
    b: np.ndarray,
    overlap_samples: int,
) -> np.ndarray:
    """Cross-fade two 1-D arrays over `overlap_samples`."""

    a = np.asarray(a, dtype=np.float32).reshape(-1)
    b = np.asarray(b, dtype=np.float32).reshape(-1)
    if overlap_samples <= 0 or a.size < overlap_samples or b.size < overlap_samples:
        return np.concatenate([a, b]).astype(np.float32)
    ramp_up = np.linspace(0.0, 1.0, overlap_samples, dtype=np.float32)
    ramp_down = 1.0 - ramp_up
    a[-overlap_samples:] = a[-overlap_samples:] * ramp_down
    b[:overlap_samples] = b[:overlap_samples] * ramp_up
    return np.concatenate([a, b[overlap_samples:]]).astype(np.float32)


class ResembleDenoiser:
    """Singleton ONNX-based resemble audio denoiser.

    Only DirectML is supported — CPU fallback is *disabled* because
    a software denoiser running on CPU would be too slow for a
    web-serving pipeline.
    """

    _instance: Optional["ResembleDenoiser"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._session = None
        self._session_lock = threading.Lock()
        self._providers: List[str] = []
        self._provider_label: str = "unloaded"
        self._last_error: Optional[str] = None
        self._model_path: Optional[Path] = None
        self._input_name: Optional[str] = None
        self._output_name: Optional[str] = None

    # -------------------------------------------------------------------
    # Singleton
    # -------------------------------------------------------------------
    @classmethod
    def instance(cls) -> "ResembleDenoiser":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def is_loaded(self) -> bool:
        return self._session is not None

    def is_directml_ready(self) -> Tuple[bool, str]:
        try:
            return onnx_provider.is_directml_available()
        except Exception as exc:
            return (False, f"directml probe failed: {exc}")

    def last_error(self) -> Optional[str]:
        return self._last_error

    def providers(self) -> List[str]:
        return list(self._providers)

    def provider_label(self) -> str:
        return self._provider_label

    def model_path(self) -> Optional[Path]:
        return self._model_path

    # -------------------------------------------------------------------
    # Model discovery
    # -------------------------------------------------------------------
    def _discover_model_path(self) -> Optional[Path]:
        settings = get_settings()
        candidates: List[Path] = []
        env_dir = os.getenv("RESEMBLE_DENOISER_DIR")
        if env_dir:
            candidates.append(Path(env_dir) / DENOISER_MODEL_NAME)
        try:
            candidates.append(
                Path(settings.models_dir) / "resemble_denoiser" / DENOISER_MODEL_NAME,
            )
        except Exception:
            pass
        candidates.append(
            Path("/workspace/models/resemble_denoiser") / DENOISER_MODEL_NAME,
        )
        for p in candidates:
            if p.exists():
                return p
        return None

    # -------------------------------------------------------------------
    # Warmup
    # -------------------------------------------------------------------
    def warmup(self) -> bool:
        with self._session_lock:
            if self.is_loaded():
                return True
            ort = _try_import_ort()
            if ort is None:
                self._last_error = "onnxruntime not importable"
                _logger.warning(
                    "resemble_denoiser warmup skipped: onnxruntime unavailable",
                    extra={"stage": "resemble_denoiser.warmup"},
                )
                return False
            model_path = self._discover_model_path()
            if model_path is None:
                self._last_error = "denoiser model not found (resemble_denoiser.onnx)"
                _logger.info(
                    "resemble_denoiser: model file not found — denoising will be a no-op",
                    extra={"stage": "resemble_denoiser.warmup"},
                )
                return False
            try:
                providers, label = onnx_provider.select_providers()
            except DirectMLNotAvailable as exc:
                self._last_error = f"directml_unavailable: {exc}"
                _logger.error(
                    "resemble_denoiser warmup aborted: DirectML unavailable (%s)",
                    exc,
                    extra={
                        "stage": "resemble_denoiser.warmup",
                        "error_code": "directml_unavailable",
                    },
                )
                return False
            if "DmlExecutionProvider" not in providers:
                self._last_error = (
                    "resemble_denoiser: selected providers lack DirectML; "
                    "refusing CPU fallback"
                )
                _logger.error(
                    "resemble_denoiser warmup aborted: providers=%s lacks DirectML",
                    providers,
                    extra={
                        "stage": "resemble_denoiser.warmup",
                        "error_code": "directml_unavailable",
                    },
                )
                return False
            self._providers = list(providers)
            self._provider_label = label
            session_options = _build_session_options(ort)
            if session_options is not None:
                _logger.info(
                    "resemble_denoiser session configured with ORT_SEQUENTIAL (DirectML safe)",
                    extra={
                        "stage": "resemble_denoiser.session_options",
                        "providers": self._providers,
                        "provider_label": self._provider_label,
                    },
                )
            try:
                self._session = _create_inference_session(
                    ort, str(model_path), list(providers), session_options,
                )
            except Exception as exc:
                self._last_error = f"denoiser session failed: {exc}"
                _logger.exception("resemble_denoiser session create failed: %s", exc)
                self._session = None
                return False
            self._model_path = model_path
            try:
                self._input_name = self._session.get_inputs()[0].name
                self._output_name = self._session.get_outputs()[0].name
            except Exception as exc:
                _logger.warning("resemble_denoiser: failed to read I/O metadata: %s", exc)
            _logger.info(
                "resemble_denoiser model loaded",
                extra={
                    "stage": "resemble_denoiser.warmup",
                    "model": str(model_path),
                    "providers": self._providers,
                    "input_name": self._input_name,
                    "output_name": self._output_name,
                },
            )
            return True

    # -------------------------------------------------------------------
    # Denoise
    # -------------------------------------------------------------------
    def denoise(
        self,
        audio: np.ndarray,
        sample_rate: int = DENOISER_SAMPLE_RATE,
    ) -> np.ndarray:
        """Apply resemble denoising to the *vocals* (not the full mix).

        If the denoiser model is not loaded this is a no-op —
        the original audio is returned unchanged.

        Parameters
        ----------
        audio : np.ndarray
            1-D float32 waveform (mono).  Expected sample rate: 16 kHz.
        sample_rate : int
            Sample rate of `audio`.

        Returns
        -------
        np.ndarray
            Denoised waveform, same length and dtype as input.
        """
        if not self.is_loaded():
            return np.asarray(audio, dtype=np.float32)

        arr = np.asarray(audio, dtype=np.float32).reshape(-1)
        if arr.size == 0:
            return arr

        chunk_samples = int(DENOISER_CHUNK_SEC * sample_rate)
        overlap_samples = int(DENOISER_OVERLAP_SEC * sample_rate)
        if chunk_samples <= 0 or overlap_samples <= 0:
            return arr

        if arr.size <= chunk_samples:
            return self._denoise_chunk(arr)

        # Sliding window with cross-fade
        step = max(1, chunk_samples - overlap_samples)
        denoised: Optional[np.ndarray] = None
        for start in range(0, arr.size, step):
            end = min(start + chunk_samples, arr.size)
            chunk = arr[start:end]
            if chunk.size < chunk_samples and denoised is not None:
                # Last partial chunk — just append (no cross-fade needed)
                d_chunk = self._denoise_chunk(chunk)
                denoised = np.concatenate([denoised, d_chunk]).astype(np.float32)
                break
            d_chunk = self._denoise_chunk(chunk)
            if denoised is None:
                denoised = d_chunk
            else:
                denoised = _linear_crossfade(denoised, d_chunk, overlap_samples)

        if denoised is None:
            return arr
        # Trim to original length
        if denoised.size > arr.size:
            denoised = denoised[: arr.size]
        elif denoised.size < arr.size:
            denoised = np.pad(denoised, (0, arr.size - denoised.size), mode="edge")
        return denoised.astype(np.float32)

    def _denoise_chunk(self, chunk: np.ndarray) -> np.ndarray:
        """Run the ONNX denoiser on a single chunk."""
        if self._session is None:
            return chunk
        # The model expects (batch=1, samples) or (batch=1, 1, samples)
        inp = chunk.astype(np.float32).reshape(1, -1)
        try:
            outs = self._session.run(
                [self._output_name] if self._output_name else None,
                {self._input_name: inp} if self._input_name else None,
            )
        except Exception as exc:
            _logger.warning("resemble_denoiser inference failed: %s", exc)
            return chunk
        if not outs or len(outs) == 0:
            return chunk
        out = np.asarray(outs[0], dtype=np.float32).reshape(-1)
        if out.size != chunk.size:
            if out.size < chunk.size:
                out = np.pad(out, (0, chunk.size - out.size), mode="edge")
            else:
                out = out[: chunk.size]
        return out.astype(np.float32)


def get_resemble_denoiser() -> ResembleDenoiser:
    return ResembleDenoiser.instance()