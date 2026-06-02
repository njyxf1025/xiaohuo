from __future__ import annotations

from typing import Tuple

import numpy as np

from core.logging import get_logger

_logger = get_logger("utils.mel")

MEL_SPEC_PARAMS = {
    "n_fft": 800,
    "hop_length": 200,
    "win_length": 800,
    "n_mels": 80,
    "sample_rate": 16000,
    "fmin": 55.0,
    "fmax": 7600.0,
    "min_value": -4.0,
    "max_value": 4.0,
    "preemphasis": 0.97,
}

EXPECTED_CHUNK_FRAMES = 16


def _hann_window(win_length: int) -> np.ndarray:
    n = int(win_length)
    if n <= 1:
        return np.ones(n, dtype=np.float32)
    return np.hanning(n).astype(np.float32)


def _pad_audio(wav: np.ndarray) -> np.ndarray:
    arr = np.asarray(wav, dtype=np.float32).reshape(-1)
    if arr.size == 0:
        return arr
    pad = MEL_SPEC_PARAMS["win_length"] // 2
    return np.pad(arr, (pad, pad), mode="reflect")


def _preemphasis(wav: np.ndarray, coeff: float) -> np.ndarray:
    arr = np.asarray(wav, dtype=np.float32).reshape(-1)
    if arr.size == 0 or coeff <= 0:
        return arr
    out = np.empty_like(arr)
    out[0] = arr[0]
    out[1:] = arr[1:] - coeff * arr[:-1]
    return out


def _stft_magnitude(wav: np.ndarray) -> np.ndarray:
    n_fft = int(MEL_SPEC_PARAMS["n_fft"])
    hop = int(MEL_SPEC_PARAMS["hop_length"])
    win_length = int(MEL_SPEC_PARAMS["win_length"])
    padded = _pad_audio(wav)
    if padded.size < n_fft:
        pad = n_fft - padded.size
        padded = np.pad(padded, (0, pad), mode="constant")
    window = _hann_window(win_length)
    if window.size < n_fft:
        window = np.pad(window, (0, n_fft - window.size), mode="constant")
    elif window.size > n_fft:
        window = window[:n_fft]
    n_frames = 1 + max(0, (padded.size - n_fft) // hop)
    if n_frames <= 0:
        return np.zeros((n_fft // 2 + 1, 0), dtype=np.float32)
    strides = padded.strides + (hop * padded.strides[-1],)
    shape = (n_frames, n_fft)
    frames = np.lib.stride_tricks.as_strided(padded, shape=shape, strides=strides)
    frames = frames.copy()
    frames *= window
    spec = np.fft.rfft(frames, n=n_fft, axis=-1)
    mag = np.abs(spec).astype(np.float32)
    return mag.T


def _slaney_mel_filts(n_mels: int, n_fft: int, sample_rate: int, fmin: float, fmax: float) -> np.ndarray:
    try:
        import librosa
        return librosa.filters.mel(
            sr=sample_rate,
            n_fft=n_fft,
            n_mels=n_mels,
            fmin=fmin,
            fmax=fmax,
            htk=False,
            norm="slaney",
        ).astype(np.float32)
    except Exception:
        low_freq = float(fmin)
        high_freq = float(fmax) if fmax else float(sample_rate) / 2.0
        fft_freqs = np.linspace(0.0, float(sample_rate) / 2.0, n_fft // 2 + 1, dtype=np.float32)
        mel_low = 2595.0 * np.log10(1.0 + low_freq / 700.0)
        mel_high = 2595.0 * np.log10(1.0 + high_freq / 700.0)
        mel_points = np.linspace(mel_low, mel_high, n_mels + 2, dtype=np.float32)
        hz_points = 700.0 * (10.0 ** (mel_points / 2595.0) - 1.0)
        filters = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
        for m in range(1, n_mels + 1):
            f_left = hz_points[m - 1]
            f_center = hz_points[m]
            f_right = hz_points[m + 1]
            for k, f in enumerate(fft_freqs):
                if f >= f_left and f <= f_center:
                    filters[m - 1, k] = (f - f_left) / max(1e-6, f_center - f_left)
                elif f > f_center and f <= f_right:
                    filters[m - 1, k] = (f_right - f) / max(1e-6, f_right - f_center)
        return filters


def _power_to_db(mel_power: np.ndarray, ref: float = 1.0, amin: float = 1e-10, top_db: float = 80.0) -> np.ndarray:
    arr = np.asarray(mel_power, dtype=np.float32)
    log_spec = 10.0 * np.log10(np.maximum(amin, arr) / max(amin, ref))
    if top_db is not None and top_db > 0:
        log_spec = np.maximum(log_spec, log_spec.max() - top_db)
    return log_spec.astype(np.float32)


def compute_mel(wav: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    if wav is None:
        raise ValueError("wav is None")
    target_sr = int(MEL_SPEC_PARAMS["sample_rate"])
    if int(sample_rate) != target_sr:
        try:
            import librosa

            wav = librosa.resample(
                np.asarray(wav, dtype=np.float32),
                orig_sr=int(sample_rate),
                target_sr=target_sr,
                res_type="kaiser_fast",
            )
        except Exception as exc:
            _logger.warning("librosa resample unavailable, using simple linear resample: %s", exc)
            ratio = target_sr / float(sample_rate) if sample_rate > 0 else 1.0
            n_new = max(1, int(round(wav.shape[-1] * ratio)))
            wav = np.interp(
                np.linspace(0.0, 1.0, n_new, dtype=np.float32),
                np.linspace(0.0, 1.0, wav.shape[-1], dtype=np.float32),
                wav,
            ).astype(np.float32)

    arr = np.asarray(wav, dtype=np.float32).reshape(-1)
    if arr.size == 0:
        return np.zeros((MEL_SPEC_PARAMS["n_mels"], 0), dtype=np.float32)

    arr = _preemphasis(arr, float(MEL_SPEC_PARAMS["preemphasis"]))
    spec = _stft_magnitude(arr)
    if spec.size == 0:
        return np.zeros((MEL_SPEC_PARAMS["n_mels"], 0), dtype=np.float32)

    n_mels = int(MEL_SPEC_PARAMS["n_mels"])
    n_fft = int(MEL_SPEC_PARAMS["n_fft"])
    mel_filts = _slaney_mel_filts(
        n_mels=n_mels,
        n_fft=n_fft,
        sample_rate=target_sr,
        fmin=float(MEL_SPEC_PARAMS["fmin"]),
        fmax=float(MEL_SPEC_PARAMS["fmax"]),
    )
    mel_power = mel_filts @ spec
    mel_power = np.maximum(mel_power, 1e-10)
    mel_db = _power_to_db(mel_power, ref=1.0, amin=1e-10, top_db=80.0)

    mel_db = (mel_db + 4.0) / 4.0
    mel_db = np.clip(
        mel_db,
        float(MEL_SPEC_PARAMS["min_value"]),
        float(MEL_SPEC_PARAMS["max_value"]),
    )
    return mel_db.astype(np.float32)


def mel_chunks_for_video(
    mel: np.ndarray,
    num_video_frames: int,
    fps: int = 25,
) -> np.ndarray:
    if mel is None or mel.size == 0:
        return np.zeros((int(MEL_SPEC_PARAMS["n_mels"]), 0), dtype=np.float32)
    arr = np.asarray(mel, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1).T
    if arr.ndim == 3:
        arr = arr[0]
    hop = int(MEL_SPEC_PARAMS["hop_length"])
    sr = int(MEL_SPEC_PARAMS["sample_rate"])
    samples_per_frame = sr // max(1, int(fps))
    mel_per_frame = max(1, int(round(samples_per_frame / float(hop))))
    target_mel_len = int(num_video_frames) * mel_per_frame
    if arr.shape[-1] >= target_mel_len:
        cropped = arr[:, :target_mel_len]
    else:
        pad = target_mel_len - arr.shape[-1]
        cropped = np.pad(arr, ((0, 0), (0, pad)), mode="edge")
    return cropped.astype(np.float32)


def split_mel_chunks(mel: np.ndarray, chunk_frames: int = EXPECTED_CHUNK_FRAMES) -> np.ndarray:
    if mel is None or mel.size == 0:
        return np.zeros((int(MEL_SPEC_PARAMS["n_mels"]), 0, int(chunk_frames)), dtype=np.float32)
    arr = np.asarray(mel, dtype=np.float32)
    n_time = arr.shape[-1]
    chunk = int(chunk_frames)
    usable = (n_time // chunk) * chunk
    if usable <= 0:
        padded = np.pad(arr, ((0, 0), (0, chunk - n_time)), mode="edge")
        return padded[:, :chunk].reshape(arr.shape[0], 1, chunk)
    trimmed = arr[:, :usable]
    n_groups = usable // chunk
    return trimmed.reshape(arr.shape[0], n_groups, chunk)
