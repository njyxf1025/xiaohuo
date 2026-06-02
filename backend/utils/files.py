from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Tuple

import aiofiles

from core.config import get_settings
from core.logging import get_logger

_logger = get_logger("utils.files")

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_basename(name: str) -> str:
    base = Path(name or "").name
    base = _SAFE_NAME.sub("_", base).strip("._-")
    if not base:
        base = f"file_{int(time.time() * 1000)}"
    return base[:160]


def split_ext(name: str) -> Tuple[str, str]:
    p = Path(name or "")
    suffix = p.suffix.lower().lstrip(".")
    stem = p.stem
    return stem, suffix


def music_storage_dir() -> Path:
    settings = get_settings()
    data_dir = settings.resolved_data_dir()
    target = data_dir / "uploads" / "music"
    target.mkdir(parents=True, exist_ok=True)
    return target


def music_file_path(music_id: str, ext: str) -> Path:
    ext = (ext or "").lower().lstrip(".")
    safe_id = _SAFE_NAME.sub("", music_id) or "unknown"
    return music_storage_dir() / f"{safe_id}.{ext or 'bin'}"


def slice_file_path(music_id: str, slice_id: str, ext: str) -> Path:
    ext = (ext or "").lower().lstrip(".")
    safe_music = _SAFE_NAME.sub("", music_id) or "unknown"
    safe_slice = _SAFE_NAME.sub("", slice_id) or "slice"
    return music_storage_dir() / f"{safe_music}_slice_{safe_slice}.{ext or 'wav'}"


def find_music_file(music_id: str) -> Path | None:
    target_dir = music_storage_dir()
    safe_id = _SAFE_NAME.sub("", music_id)
    if not safe_id:
        return None
    for path in target_dir.glob(f"{safe_id}.*"):
        if path.is_file():
            return path
    return None


def find_slice_file(slice_id: str) -> Path | None:
    target_dir = music_storage_dir()
    safe_slice = _SAFE_NAME.sub("", slice_id)
    if not safe_slice:
        return None
    matches = sorted(target_dir.glob(f"*_slice_{safe_slice}.*"))
    for path in matches:
        if path.is_file():
            return path
    return None


async def write_bytes_async(target: Path, data: bytes) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(target, "wb") as f:
        await f.write(data)
    return target.stat().st_size


def write_bytes(target: Path, data: bytes) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as f:
        written = f.write(data)
    return written


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError as exc:
        _logger.warning("stat failed for %s: %s", path, exc)
        return 0
