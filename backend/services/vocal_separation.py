from __future__ import annotations

import os
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np

from core import onnx_provider
from core.config import get_settings
from core.logging import get_logger
from core.onnx_provider import DirectMLNotAvailable

_logger = get_logger("services.vocal_separation")


class VocalSeparationError(RuntimeError):
    pass


class VocalSeparationDirectMLNotAvailable(VocalSeparationError):
    code = "directml_unavailable"


class VocalSeparationModelNotLoaded(VocalSeparationError):
    code = "vocal_separation_model_not_loaded"


DEFAULT_CANDIDATE_NAMES: Tuple[str, ...] = (
    "vocal_separation.onnx",
    "mel_band_roformer.onnx",
    "htdemucs.onnx",
    "spleeter_2stems.onnx",
    "mdx_q.onnx",
    "kim_vocal.onnx",
    "vocal_separation_hq.onnx",
)


@dataclass
class VocalSeparationPaths:
    model_path: Path

    def is_complete(self) -> bool:
        return self.model_path is not None and self.model_path.exists()


def _try_import_ort():
    try:
        import onnxruntime as ort
        return ort
    except Exception as exc:
        _logger.warning("onnxruntime import failed: %s", exc)
        return None


def _try_import_sf():
    try:
        import soundfile as sf
        return sf
    except Exception as exc:
        _logger.warning("soundfile import failed: %s", exc)
        return None


def _build_session_options(ort):
    try:
        session_options = ort.SessionOptions()
        session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        return session_options
    except Exception as exc:
        _logger.warning(
            "vocal_separation: failed to build sequential SessionOptions, falling back: %s",
            exc,
            extra={"stage": "vocal_separation.session_options"},
        )
        try:
            return ort.SessionOptions()
        except Exception as inner_exc:
            _logger.warning(
                "vocal_separation: ort.SessionOptions() unavailable: %s",
                inner_exc,
                extra={"stage": "vocal_separation.session_options"},
            )
            return None


def _create_inference_session(ort, model_path: str, providers: List[str], session_options):
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


def _read_wav_mono(path: str, target_sr: int = 44100) -> np.ndarray:
    sf = _try_import_sf()
    if sf is None:
        raise VocalSeparationError("soundfile unavailable; cannot read audio")
    wav, sr = sf.read(path, always_2d=False, dtype="float32")
    if wav.ndim == 2:
        wav = wav.mean(axis=1).astype("float32")
    else:
        wav = wav.astype("float32")
    if sr != target_sr:
        try:
            import scipy.signal as sps

            new_len = int(round(len(wav) * float(target_sr) / float(sr)))
            wav = sps.resample(wav, new_len).astype("float32")
        except Exception:
            g = float(target_sr) / float(sr)
            idx = (np.arange(int(len(wav) * g)) / g).astype(np.int64)
            idx = np.clip(idx, 0, len(wav) - 1)
            wav = wav[idx].astype("float32")
    return wav


def _write_wav(path: str, wav: np.ndarray, sample_rate: int) -> None:
    sf = _try_import_sf()
    if sf is None:
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            pcm = np.clip(wav, -1.0, 1.0)
            pcm = (pcm * 32767.0).astype(np.int16).tobytes()
            wf.writeframes(pcm)
        return
    sf.write(path, wav.astype("float32"), sample_rate, subtype="FLOAT")


class VocalSeparator:
    _instance: Optional["VocalSeparator"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._session = None
        self._session_lock = threading.Lock()
        self._providers: List[str] = []
        self._provider_label: str = "unloaded"
        self._last_error: Optional[str] = None
        self._paths: Optional[VocalSeparationPaths] = None
        self._input_name: Optional[str] = None
        self._output_names: List[str] = []
        self._stems_hint: int = 2
        self._sample_rate_hint: int = 44100

    @classmethod
    def instance(cls) -> "VocalSeparator":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = VocalSeparator()
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

    def model_paths(self) -> Optional[VocalSeparationPaths]:
        return self._paths

    def _discover_model_path(self) -> Optional[Path]:
        settings = get_settings()
        roots: List[Path] = []
        env_root = os.getenv("VOCAL_SEPARATION_DIR")
        if env_root:
            roots.append(Path(env_root))
        try:
            models_dir = Path(settings.models_dir)
            roots.append(models_dir / "vocal_separation")
        except Exception:
            pass
        roots.append(Path("/workspace/models/vocal_separation"))
        seen: set = set()
        for root in roots:
            try:
                if not root.exists():
                    continue
            except Exception:
                continue
            if root in seen:
                continue
            seen.add(root)
            for name in DEFAULT_CANDIDATE_NAMES:
                p = root / name
                if p.exists():
                    return p
        return None

    def warmup(self) -> bool:
        with self._session_lock:
            if self.is_loaded():
                return True
            ort = _try_import_ort()
            if ort is None:
                self._last_error = "onnxruntime not importable"
                _logger.warning(
                    "vocal_separation warmup skipped: onnxruntime unavailable",
                    extra={"stage": "vocal_separation.warmup"},
                )
                return False
            model_path = self._discover_model_path()
            if model_path is None:
                self._last_error = "vocal_separation model not found"
                _logger.warning(
                    "vocal_separation warmup skipped: no model file under models/vocal_separation/",
                    extra={"stage": "vocal_separation.warmup"},
                )
                return False
            try:
                providers, label = onnx_provider.select_providers()
            except DirectMLNotAvailable as exc:
                self._last_error = f"directml_unavailable: {exc}"
                _logger.error(
                    "vocal_separation warmup aborted: DirectML unavailable (%s)",
                    exc,
                    extra={
                        "stage": "vocal_separation.warmup",
                        "error_code": "directml_unavailable",
                    },
                )
                return False
            if "DmlExecutionProvider" not in providers:
                self._last_error = (
                    "vocal_separation: selected providers lack DirectML; "
                    "refusing CPU fallback"
                )
                _logger.error(
                    "vocal_separation warmup aborted: providers=%s lacks DirectML",
                    providers,
                    extra={
                        "stage": "vocal_separation.warmup",
                        "error_code": "directml_unavailable",
                    },
                )
                return False
            self._providers = list(providers)
            self._provider_label = label
            session_options = _build_session_options(ort)
            if session_options is not None:
                _logger.info(
                    "vocal_separation session configured with ORT_SEQUENTIAL (DirectML safe)",
                    extra={
                        "stage": "vocal_separation.session_options",
                        "providers": self._providers,
                        "provider_label": self._provider_label,
                    },
                )
            try:
                self._session = _create_inference_session(
                    ort, str(model_path), list(providers), session_options,
                )
            except Exception as exc:
                self._last_error = f"vocal_separation session failed: {exc}"
                _logger.exception("vocal_separation session create failed: %s", exc)
                self._session = None
                return False
            self._paths = VocalSeparationPaths(model_path=model_path)
            try:
                self._input_name = self._session.get_inputs()[0].name
                self._output_names = [o.name for o in self._session.get_outputs()]
            except Exception as exc:
                _logger.warning("vocal_separation: failed to read I/O metadata: %s", exc)
            _logger.info(
                "vocal_separation model loaded",
                extra={
                    "stage": "vocal_separation.warmup",
                    "model": str(model_path),
                    "providers": self._providers,
                    "input_name": self._input_name,
                    "outputs": self._output_names,
                },
            )
            return True

    def _post_process(self, raw_outputs: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        if not raw_outputs:
            raise VocalSeparationError("vocal_separation: model produced no outputs")
        vocals = None
        accompaniment = None
        for idx, out in enumerate(raw_outputs):
            arr = np.asarray(out)
            if arr.ndim == 3 and arr.shape[-1] >= 2:
                vocals = arr[..., 0].squeeze().astype("float32")
                accompaniment = arr[..., 1].squeeze().astype("float32")
                break
            if arr.ndim == 4 and arr.shape[-1] >= 2:
                vocals = arr[0, ..., 0].astype("float32")
                accompaniment = arr[0, ..., 1].astype("float32")
                break
        if vocals is None:
            primary = np.asarray(raw_outputs[0])
            primary = primary.squeeze().astype("float32")
            mid = primary.shape[-1] // 2 if primary.ndim > 1 else primary.shape[0] // 2
            if primary.ndim == 1:
                vocals = primary
                accompaniment = np.zeros_like(primary)
            else:
                if primary.ndim == 2:
                    vocals = primary[..., 0] if primary.shape[-1] > 1 else primary[:, 0]
                elif primary.ndim == 3:
                    vocals = primary[0, ..., 0] if primary.shape[-1] > 1 else primary[0, :, 0]
                else:
                    vocals = primary.reshape(-1)
                accompaniment = np.zeros_like(vocals)
            _logger.info(
                "vocal_separation: 1-stem model; using model output as vocals, "
                "synthesizing silent accompaniment (lipsync will be on vocals only)",
                extra={"stage": "vocal_separation.postprocess", "outputs": len(raw_outputs)},
            )
        vocals = np.clip(vocals, -1.0, 1.0).astype("float32")
        accompaniment = np.clip(accompaniment, -1.0, 1.0).astype("float32")
        if vocals.shape != accompaniment.shape:
            n = min(len(vocals), len(accompaniment))
            vocals = vocals[:n]
            accompaniment = accompaniment[:n]
        return vocals, accompaniment

    def separate(
        self,
        audio_path: str,
        output_dir: str,
        progress_cb: Optional[Callable[[str, float, str], None]] = None,
    ) -> Tuple[str, Optional[str]]:
        if not os.path.exists(audio_path):
            raise VocalSeparationError(f"audio not found: {audio_path}")
        os.makedirs(output_dir, exist_ok=True)
        if progress_cb is not None:
            progress_cb("vocal_separation.loading", 12.0, "loading audio for vocal separation")
        try:
            wav = _read_wav_mono(audio_path, target_sr=44100)
        except Exception as exc:
            raise VocalSeparationError(f"failed to read audio: {exc}") from exc
        if progress_cb is not None:
            progress_cb("vocal_separation.audio_loaded", 16.0, "audio loaded for separation")
        if not self.is_loaded():
            try:
                ok = self.warmup()
            except VocalSeparationDirectMLNotAvailable:
                raise
            if not ok or not self.is_loaded():
                last = self._last_error or "unknown"
                if "directml" in last.lower():
                    raise VocalSeparationDirectMLNotAvailable(last)
                if "model" in last.lower() and "not" in last.lower():
                    raise VocalSeparationModelNotLoaded(last)
                raise VocalSeparationError(f"vocal_separation not ready: {last}")
        if progress_cb is not None:
            progress_cb(
                "vocal_separation.inferring", 20.0,
                f"running vocal separation on DirectML ({len(wav)} samples)",
            )
        start = time.perf_counter()
        try:
            chunk = 44100 * 30
            vocals_chunks: List[np.ndarray] = []
            acc_chunks: List[np.ndarray] = []
            total_chunks = max(1, (len(wav) + chunk - 1) // chunk)
            for i in range(0, len(wav), chunk):
                seg = wav[i:i + chunk]
                inputs = {self._input_name: seg[None, :].astype("float32")}
                outs = self._session.run(self._output_names, inputs)
                v, a = self._post_process(outs)
                vocals_chunks.append(v)
                acc_chunks.append(a)
                if progress_cb is not None:
                    pct = 20.0 + 50.0 * (len(vocals_chunks) / total_chunks)
                    progress_cb(
                        "vocal_separation.inferring",
                        float(min(70.0, pct)),
                        f"vocal separation chunk {len(vocals_chunks)}/{total_chunks}",
                    )
            vocals = np.concatenate(vocals_chunks).astype("float32")
            accompaniment = np.concatenate(acc_chunks).astype("float32")
        except VocalSeparationDirectMLNotAvailable:
            raise
        except Exception as exc:
            _logger.exception("vocal_separation inference failed: %s", exc)
            raise VocalSeparationError(f"vocal_separation inference failed: {exc}") from exc
        duration = time.perf_counter() - start
        _logger.info(
            "vocal_separation inference complete",
            extra={
                "stage": "vocal_separation.inference",
                "duration_ms": round(duration * 1000, 1),
                "vocals_samples": int(len(vocals)),
                "accompaniment_samples": int(len(accompaniment)),
                "providers": self._providers,
            },
        )
        base = Path(audio_path).stem
        vocals_path = os.path.join(output_dir, f"{base}__vocals.wav")
        accompaniment_path = os.path.join(output_dir, f"{base}__accompaniment.wav")
        _write_wav(vocals_path, vocals, 44100)
        _write_wav(accompaniment_path, accompaniment, 44100)
        if progress_cb is not None:
            progress_cb(
                "vocal_separation.done", 75.0,
                "vocal separation finished; using vocals for Wav2Lip",
            )
        return vocals_path, accompaniment_path


def get_vocal_separator() -> VocalSeparator:
    return VocalSeparator.instance()
