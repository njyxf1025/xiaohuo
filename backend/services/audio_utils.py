from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np

from core.logging import get_logger

_logger = get_logger("services.audio_utils")

DEFAULT_SR = 22050
DEFAULT_CHANNELS = 1

SUPPORTED_EXTENSIONS = ("mp3", "wav", "m4a", "flac", "ogg", "aac")
SUPPORTED_MIME_HINTS = (
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mp4",
    "audio/x-m4a",
    "audio/flac",
    "audio/x-flac",
    "audio/ogg",
    "audio/aac",
    "application/octet-stream",
)


@dataclass
class AudioInfo:
    duration_sec: float
    sample_rate: int
    channels: int
    samples: int
    file_path: Path


def is_supported_extension(ext: str) -> bool:
    if not ext:
        return False
    return ext.lower().lstrip(".") in SUPPORTED_EXTENSIONS


def is_supported_mime(mime: str) -> bool:
    if not mime:
        return True
    m = mime.lower().strip()
    if m.startswith("audio/"):
        return True
    return m in SUPPORTED_MIME_HINTS


def probe_audio(path: Path, target_sr: int = DEFAULT_SR) -> AudioInfo:
    import librosa

    try:
        y, sr = librosa.load(str(path), sr=target_sr, mono=False)
    except Exception as exc:
        _logger.exception("librosa.load failed for %s: %s", path, exc)
        raise

    if y.ndim == 1:
        channels = 1
        samples = int(y.shape[0])
    else:
        channels = int(y.shape[0])
        samples = int(y.shape[1])

    duration_sec = float(samples) / float(sr) if sr else 0.0
    return AudioInfo(
        duration_sec=duration_sec,
        sample_rate=int(sr),
        channels=channels,
        samples=samples,
        file_path=path,
    )


def load_mono(path: Path, target_sr: int = DEFAULT_SR) -> Tuple[np.ndarray, int]:
    import librosa

    y, sr = librosa.load(str(path), sr=target_sr, mono=True)
    return np.asarray(y, dtype=np.float32), int(sr)


def load_native(path: Path) -> Tuple[np.ndarray, int]:
    import librosa

    y, sr = librosa.load(str(path), sr=None, mono=False)
    if y.ndim == 1:
        return np.asarray(y, dtype=np.float32), int(sr)
    return np.asarray(y, dtype=np.float32), int(sr)


def compute_peaks(samples: np.ndarray, num_peaks: int) -> List[float]:
    if samples is None or samples.size == 0 or num_peaks <= 0:
        return []
    arr = np.abs(samples.astype(np.float32, copy=False))
    n = arr.size
    if num_peaks >= n:
        reduced = arr
        return [float(x) for x in reduced.tolist()]
    window = n // num_peaks
    if window <= 0:
        window = 1
    usable = window * num_peaks
    trimmed = arr[:usable]
    if trimmed.size < usable:
        padded = np.zeros(usable, dtype=arr.dtype)
        padded[: trimmed.size] = trimmed
        trimmed = padded
    reshaped = trimmed.reshape(num_peaks, window)
    peaks = reshaped.max(axis=1)
    return [float(p) for p in peaks.tolist()]


def compute_peaks_minmax(samples: np.ndarray, num_peaks: int) -> List[float]:
    if samples is None or samples.size == 0 or num_peaks <= 0:
        return []
    n = samples.size
    if num_peaks >= n:
        return [float(samples[i]) for i in range(n)]
    window = n // num_peaks
    if window <= 0:
        window = 1
    usable = window * num_peaks
    if usable < n:
        arr = samples[:usable]
    else:
        arr = samples
    if arr.size < usable:
        pad = np.zeros(usable - arr.size, dtype=arr.dtype)
        arr = np.concatenate([arr, pad])
    reshaped = arr.reshape(num_peaks, window).astype(np.float32, copy=False)
    mins = reshaped.min(axis=1)
    maxs = reshaped.max(axis=1)
    out: List[float] = []
    for mn, mx in zip(mins, maxs):
        amp = max(abs(float(mn)), abs(float(mx)))
        out.append(amp)
    return out


def write_wav(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    import soundfile as sf

    path.parent.mkdir(parents=True, exist_ok=True)
    if samples.ndim > 1:
        arr = samples.T if samples.shape[0] < samples.shape[1] else samples
    else:
        arr = samples
    sf.write(str(path), arr, sample_rate, subtype="PCM_16")


def slice_samples(
    samples: np.ndarray,
    sample_rate: int,
    start_sec: float,
    end_sec: float,
) -> np.ndarray:
    if samples is None or samples.size == 0:
        return np.zeros((0,), dtype=np.float32)
    if end_sec <= start_sec:
        return np.zeros((0,), dtype=np.float32)
    start_idx = max(0, int(start_sec * sample_rate))
    end_idx = min(samples.shape[-1], int(end_sec * sample_rate))
    if end_idx <= start_idx:
        return np.zeros((0,), dtype=np.float32)
    if samples.ndim == 1:
        return samples[start_idx:end_idx].astype(np.float32, copy=False)
    return samples[:, start_idx:end_idx].astype(np.float32, copy=False)


def loudest_window(
    samples: np.ndarray,
    sample_rate: int,
    window_sec: float = 20.0,
) -> Tuple[float, float]:
    if samples is None or samples.size == 0 or sample_rate <= 0:
        return 0.0, 0.0
    win = int(window_sec * sample_rate)
    if win <= 0 or win >= samples.shape[-1]:
        dur = samples.shape[-1] / float(sample_rate)
        return 0.0, dur
    abs_sig = np.abs(samples if samples.ndim == 1 else samples[0]).astype(np.float32, copy=False)
    n = abs_sig.size
    if n < win:
        return 0.0, n / float(sample_rate)
    cumsum = np.concatenate([[0.0], np.cumsum(abs_sig, dtype=np.float64)])
    sums = cumsum[win:] - cumsum[:-win]
    idx = int(np.argmax(sums))
    start = idx / float(sample_rate)
    end = (idx + win) / float(sample_rate)
    return start, end
