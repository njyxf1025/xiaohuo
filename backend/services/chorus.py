from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from core.logging import get_logger
from services.audio_utils import DEFAULT_SR, load_mono, loudest_window

_logger = get_logger("services.chorus")

CHORUS_MIN_SEC = 10.0
CHORUS_MAX_SEC = 40.0
CHORUS_DEFAULT_LEN = 20.0


def _clamp_chorus(start: float, end: float, duration: float) -> Tuple[float, float]:
    if duration <= 0:
        return 0.0, 0.0
    if end <= start:
        end = start + CHORUS_MIN_SEC
    if start < 0:
        start = 0.0
    if end > duration:
        end = duration
    if start >= end:
        start = max(0.0, end - CHORUS_MIN_SEC)
    return float(start), float(end)


def _try_pychorus(
    file_path: Path,
    duration: float,
    target_length: float,
) -> Optional[Tuple[float, float, float]]:
    try:
        from pychorus import find_chorus
        from pychorus.helpers import create_chroma
    except Exception as exc:
        _logger.warning("pychorus unavailable: %s", exc)
        return None

    try:
        chroma, _wav, sr, song_length = create_chroma(str(file_path))
    except Exception as exc:
        _logger.exception("pychorus.create_chroma failed: %s", exc)
        return None

    try:
        start = find_chorus(chroma, sr, song_length, int(round(target_length)))
    except Exception as exc:
        _logger.exception("pychorus.find_chorus crashed: %s", exc)
        return None

    if start is None:
        return None
    try:
        start_f = float(start)
    except (TypeError, ValueError):
        return None
    end_f = start_f + float(target_length)
    start_f, end_f = _clamp_chorus(start_f, end_f, duration)
    return start_f, end_f, 0.85


def _fallback_loudest(file_path: Path, duration: float) -> Optional[Tuple[float, float, float]]:
    try:
        y, sr = load_mono(file_path, target_sr=DEFAULT_SR)
    except Exception as exc:
        _logger.exception("fallback loudest: failed to load %s: %s", file_path, exc)
        return None
    if y is None or y.size == 0 or duration <= 0:
        return None
    start, end = loudest_window(y, sr, window_sec=CHORUS_DEFAULT_LEN)
    if end <= start:
        return None
    start, end = _clamp_chorus(start, end, duration)
    return start, end, 0.5


def detect_chorus(
    file_path: Path,
    duration: float,
    target_length: float = CHORUS_DEFAULT_LEN,
    candidates: Optional[List[int]] = None,
) -> Optional[Tuple[float, float, float]]:
    if duration <= 0:
        _logger.warning("chorus detection skipped, invalid duration: %s", duration)
        return None

    target_length = max(CHORUS_MIN_SEC, min(CHORUS_MAX_SEC, float(target_length)))

    lengths: List[int] = []
    if candidates:
        for c in candidates:
            if c and CHORUS_MIN_SEC <= c <= CHORUS_MAX_SEC:
                lengths.append(int(c))
    if not lengths:
        lengths = [int(round(target_length))]

    best: Optional[Tuple[float, float, float, int]] = None
    for length in lengths:
        result = _try_pychorus(file_path, duration, float(length))
        if result is None:
            continue
        start, end, conf = result
        score = conf * (end - start)
        if best is None or score > best[3]:
            best = (start, end, conf, score)

    if best is not None:
        return best[0], best[1], best[2]

    _logger.info("pychorus returned nothing, using loudest-window fallback")
    return _fallback_loudest(file_path, duration)


def detect_chorus_timed(
    file_path: Path,
    duration: float,
    target_length: float = CHORUS_DEFAULT_LEN,
) -> Tuple[Optional[Tuple[float, float, float]], float]:
    start_ts = time.perf_counter()
    result = detect_chorus(file_path, duration, target_length=target_length)
    duration_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)
    _logger.info(
        "chorus detection finished",
        extra={
            "stage": "music.chorus",
            "duration_ms": duration_ms,
            "found": result is not None,
        },
    )
    return result, duration_ms
