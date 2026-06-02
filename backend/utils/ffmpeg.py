from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from core.logging import get_logger

_logger = get_logger("utils.ffmpeg")


_FFMPEG_PATH: Optional[str] = None
_FFPROBE_PATH: Optional[str] = None
_PROBED: bool = False


def _find_ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg")


def _find_ffprobe() -> Optional[str]:
    return shutil.which("ffprobe")


def probe_ffmpeg() -> bool:
    global _FFMPEG_PATH, _FFPROBE_PATH, _PROBED
    if _PROBED:
        return _FFMPEG_PATH is not None
    _FFMPEG_PATH = _find_ffmpeg()
    _FFPROBE_PATH = _find_ffprobe()
    _PROBED = True
    if _FFMPEG_PATH is None:
        _logger.warning(
            "ffmpeg CLI not found on PATH; video outputs will lack audio stream",
            extra={"stage": "ffmpeg.probe"},
        )
    else:
        _logger.info(
            "ffmpeg CLI detected",
            extra={"stage": "ffmpeg.probe", "path": _FFMPEG_PATH},
        )
    return _FFMPEG_PATH is not None


def ffmpeg_binary() -> Optional[str]:
    if not _PROBED:
        probe_ffmpeg()
    return _FFMPEG_PATH


def ffprobe_binary() -> Optional[str]:
    if not _PROBED:
        probe_ffmpeg()
    return _FFPROBE_PATH


def mux_audio_video(video_path: Path, audio_path: Path, output_path: Path) -> bool:
    ffmpeg = ffmpeg_binary()
    if ffmpeg is None:
        _logger.warning(
            "mux skipped, ffmpeg unavailable: video=%s audio=%s",
            video_path,
            audio_path,
        )
        return False
    if not Path(video_path).exists():
        _logger.warning("mux skipped, missing video: %s", video_path)
        return False
    if not Path(audio_path).exists():
        _logger.warning("mux skipped, missing audio: %s", audio_path)
        return False
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(out),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
    except Exception as exc:
        _logger.exception("ffmpeg mux crashed: %s", exc)
        return False
    if proc.returncode != 0:
        _logger.warning(
            "ffmpeg mux failed rc=%d stderr=%s",
            proc.returncode,
            (proc.stderr or "")[-400:],
        )
        return False
    _logger.info(
        "ffmpeg mux ok",
        extra={"stage": "ffmpeg.mux", "output": str(out), "size_bytes": _safe_size(out)},
    )
    return True


def _safe_size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0
