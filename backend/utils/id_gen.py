from __future__ import annotations

import uuid


def new_id(prefix: str = "", length: int = 12) -> str:
    raw = uuid.uuid4().hex
    short = raw[:length] if length and length > 0 else raw
    return f"{prefix}{short}" if prefix else short


def new_music_id() -> str:
    return new_id(prefix="mus_", length=12)


def new_slice_id() -> str:
    return new_id(prefix="slc_", length=12)
