from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from pychorus import create_chroma, find_chorus

from app.core.logger import logger

CHORUS_CLIP_LENGTH = 30
DEFAULT_CHORUS_DURATION = 30


def detect_chorus(file_path: str) -> dict:
    try:
        chroma, y, sr, song_length_sec = create_chroma(file_path)
        chorus_start = find_chorus(chroma, sr, song_length_sec, CHORUS_CLIP_LENGTH)
        if chorus_start is not None:
            end_time = min(chorus_start + CHORUS_CLIP_LENGTH, song_length_sec)
            return {
                "start_time": float(chorus_start),
                "end_time": float(end_time),
                "duration": float(end_time - chorus_start),
            }
        logger.warning(f"pychorus 未检测到高潮段落: {file_path}")
    except Exception as e:
        logger.error(f"高潮检测失败: {file_path}, 错误: {e}")
    return _default_chorus(file_path)


def _default_chorus(file_path: str) -> dict:
    try:
        y, sr = librosa.load(file_path, sr=None)
        duration = librosa.get_duration(y=y, sr=sr)
    except Exception:
        duration = 180.0
    start = max(0, (duration - DEFAULT_CHORUS_DURATION) / 2)
    end = start + DEFAULT_CHORUS_DURATION
    return {
        "start_time": float(start),
        "end_time": float(end),
        "duration": float(DEFAULT_CHORUS_DURATION),
    }


def get_audio_info(file_path: str) -> dict:
    y, sr = librosa.load(file_path, sr=None, mono=False)
    if y.ndim == 1:
        channels = 1
    else:
        channels = y.shape[0]
    duration = librosa.get_duration(y=y, sr=sr)
    suffix = Path(file_path).suffix.lstrip(".").lower()
    return {
        "duration": float(duration),
        "sample_rate": int(sr),
        "channels": channels,
        "format": suffix,
    }


def trim_audio(file_path: str, start_time: float, end_time: float, output_path: str) -> str:
    y, sr = librosa.load(file_path, sr=None, mono=False)
    start_sample = int(start_time * sr)
    end_sample = int(end_time * sr)
    end_sample = min(end_sample, y.shape[-1])
    start_sample = max(0, start_sample)
    if y.ndim == 1:
        trimmed = y[start_sample:end_sample]
    else:
        trimmed = y[:, start_sample:end_sample]
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(output_path, trimmed.T if y.ndim > 1 else trimmed, sr)
    return output_path


def get_waveform(file_path: str, num_points: int = 1000) -> list[float]:
    y, sr = librosa.load(file_path, sr=None, mono=True)
    if len(y) > num_points:
        indices = np.linspace(0, len(y) - 1, num_points, dtype=int)
        waveform = y[indices]
    else:
        waveform = y
    return waveform.tolist()
