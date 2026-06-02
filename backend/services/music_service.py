from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.logging import get_logger
from models.schemas import ChorusSegment
from services import audio_utils
from services.audio_utils import (
    DEFAULT_SR,
    compute_peaks_minmax,
    load_mono,
    load_native,
    probe_audio,
    slice_samples,
    write_wav,
)
from services.chorus import CHORUS_DEFAULT_LEN, detect_chorus
from utils import files as file_utils
from utils.id_gen import new_music_id, new_slice_id

_logger = get_logger("services.music_service")

DEFAULT_PEAKS = 2000
MAX_PEAKS = 20000
CHORUS_CANDIDATE_LENGTHS = (20, 15, 25, 30, 10)


@dataclass
class MusicRecord:
    music_id: str
    filename: str
    extension: str
    file_path: str
    mime_type: Optional[str]
    size_bytes: int
    duration_sec: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    status: str = "uploaded"
    chorus: Optional[ChorusSegment] = None
    created_at: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.chorus is not None:
            d["chorus"] = self.chorus.model_dump()
        return d


@dataclass
class SliceRecord:
    slice_id: str
    music_id: str
    start_sec: float
    end_sec: float
    file_path: str
    extension: str
    created_at: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MusicService:
    def __init__(self) -> None:
        self._musics: Dict[str, MusicRecord] = {}
        self._slices: Dict[str, SliceRecord] = {}
        self._lock = threading.RLock()
        self._bg_tasks: Dict[str, asyncio.Task[Any]] = {}

    def list_musics(self) -> List[MusicRecord]:
        with self._lock:
            return list(self._musics.values())

    def get_music(self, music_id: str) -> Optional[MusicRecord]:
        with self._lock:
            return self._musics.get(music_id)

    def get_slice(self, slice_id: str) -> Optional[SliceRecord]:
        with self._lock:
            return self._slices.get(slice_id)

    @staticmethod
    def _resolve_extension(filename: str, content_type: Optional[str]) -> str:
        _, ext = file_utils.split_ext(filename or "")
        if ext:
            return ext
        ct = (content_type or "").lower()
        mapping = {
            "audio/mpeg": "mp3",
            "audio/mp3": "mp3",
            "audio/wav": "wav",
            "audio/x-wav": "wav",
            "audio/wave": "wav",
            "audio/mp4": "m4a",
            "audio/x-m4a": "m4a",
            "audio/flac": "flac",
            "audio/x-flac": "flac",
            "audio/ogg": "ogg",
            "audio/aac": "aac",
        }
        for k, v in mapping.items():
            if k in ct:
                return v
        return "bin"

    async def upload(
        self,
        filename: str,
        content_type: Optional[str],
        data: bytes,
    ) -> MusicRecord:
        settings = get_settings()
        max_bytes = int(settings.max_upload_mb) * 1024 * 1024
        if len(data) > max_bytes:
            raise ValueError(
                f"file too large: {len(data)} bytes (max {settings.max_upload_mb} MB)"
            )

        ext = self._resolve_extension(filename, content_type)
        if not audio_utils.is_supported_extension(ext):
            raise ValueError(f"unsupported file extension: .{ext}")

        music_id = new_music_id()
        safe_name = file_utils.safe_basename(filename) or f"{music_id}.{ext}"
        target = file_utils.music_file_path(music_id, ext)

        start = time.perf_counter()
        size = await file_utils.write_bytes_async(target, data)
        write_ms = round((time.perf_counter() - start) * 1000.0, 2)
        _logger.info(
            "music file written",
            extra={
                "stage": "music.upload",
                "music_id": music_id,
                "size_bytes": size,
                "duration_ms": write_ms,
                "extension": ext,
            },
        )

        info = probe_audio(target, target_sr=DEFAULT_SR)
        record = MusicRecord(
            music_id=music_id,
            filename=safe_name,
            extension=ext,
            file_path=str(target),
            mime_type=content_type,
            size_bytes=size,
            duration_sec=float(info.duration_sec),
            sample_rate=int(info.sample_rate),
            channels=int(info.channels),
            status="ready",
        )
        with self._lock:
            self._musics[music_id] = record
        return record

    def run_chorus_detection(self, music_id: str) -> Optional[ChorusSegment]:
        record = self.get_music(music_id)
        if record is None:
            return None
        path = Path(record.file_path)
        if not path.exists():
            _logger.warning("chorus skipped, file missing: %s", path)
            return None
        try:
            result = detect_chorus(
                path,
                duration=record.duration_sec,
                target_length=CHORUS_DEFAULT_LEN,
                candidates=list(CHORUS_CANDIDATE_LENGTHS),
            )
        except Exception as exc:
            _logger.exception("chorus detection crashed for %s: %s", music_id, exc)
            return None
        if result is None:
            return None
        start, end, conf = result
        segment = ChorusSegment(
            start_sec=float(start),
            end_sec=float(end),
            confidence=float(conf),
            source="pychorus" if conf >= 0.7 else "loudest-window",
        )
        with self._lock:
            record.chorus = segment
            record.status = "ready"
        return segment

    async def schedule_chorus_detection(self, music_id: str) -> asyncio.Task[Any]:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        coro = self._async_run_chorus(music_id)
        if loop is None:
            thread = threading.Thread(target=self._sync_run_chorus, args=(music_id,), daemon=True)
            thread.start()
            with self._lock:
                self._bg_tasks[music_id] = thread
            return None
        task = loop.create_task(coro)
        with self._lock:
            self._bg_tasks[music_id] = task
        return task

    async def _async_run_chorus(self, music_id: str) -> Optional[ChorusSegment]:
        return await asyncio.to_thread(self.run_chorus_detection, music_id)

    def _sync_run_chorus(self, music_id: str) -> Optional[ChorusSegment]:
        return self.run_chorus_detection(music_id)

    def run_chorus_detection_sync(self, music_id: str) -> Optional[ChorusSegment]:
        return self.run_chorus_detection(music_id)

    def slice_audio(
        self,
        music_id: str,
        start_sec: float,
        end_sec: float,
        output_format: Optional[str] = None,
    ) -> SliceRecord:
        record = self.get_music(music_id)
        if record is None:
            raise FileNotFoundError(f"music not found: {music_id}")
        if end_sec <= start_sec:
            raise ValueError("end_sec must be greater than start_sec")
        if start_sec < 0:
            raise ValueError("start_sec must be non-negative")
        if record.duration_sec > 0 and end_sec > record.duration_sec + 0.5:
            raise ValueError("end_sec exceeds track duration")
        ext = (output_format or record.extension or "wav").lower().lstrip(".")
        if ext not in audio_utils.SUPPORTED_EXTENSIONS:
            ext = "wav"

        slice_id = new_slice_id()
        out_path = file_utils.slice_file_path(music_id, slice_id, ext)
        src_path = Path(record.file_path)
        if ext == record.extension or ext == "wav":
            if ext == "wav":
                try:
                    y, sr = load_native(src_path)
                    sliced = slice_samples(y, sr, start_sec, end_sec)
                    write_wav(out_path, sliced, sr)
                except Exception:
                    y, sr = load_mono(src_path, target_sr=DEFAULT_SR)
                    sliced = slice_samples(y, sr, start_sec, end_sec)
                    write_wav(out_path, sliced, sr)
            else:
                try:
                    from pydub import AudioSegment

                    seg = AudioSegment.from_file(str(src_path))
                    s_ms = int(max(0.0, start_sec) * 1000)
                    e_ms = int(min(len(seg), end_sec * 1000))
                    seg[s_ms:e_ms].export(str(out_path), format=ext)
                except Exception as exc:
                    _logger.warning(
                        "pydub slice failed (%s), falling back to wav", exc
                    )
                    out_path = file_utils.slice_file_path(music_id, slice_id, "wav")
                    y, sr = load_mono(src_path, target_sr=DEFAULT_SR)
                    sliced = slice_samples(y, sr, start_sec, end_sec)
                    write_wav(out_path, sliced, sr)
                    ext = "wav"
        else:
            y, sr = load_mono(src_path, target_sr=DEFAULT_SR)
            sliced = slice_samples(y, sr, start_sec, end_sec)
            write_wav(out_path, sliced, sr)
            ext = "wav"

        slice_record = SliceRecord(
            slice_id=slice_id,
            music_id=music_id,
            start_sec=float(start_sec),
            end_sec=float(end_sec),
            file_path=str(out_path),
            extension=ext,
        )
        with self._lock:
            self._slices[slice_id] = slice_record
        return slice_record

    def compute_waveform(
        self,
        music_id: str,
        num_peaks: int = DEFAULT_PEAKS,
    ) -> Optional[Dict[str, Any]]:
        record = self.get_music(music_id)
        if record is None:
            return None
        try:
            num_peaks = int(num_peaks)
        except (TypeError, ValueError):
            num_peaks = DEFAULT_PEAKS
        num_peaks = max(50, min(MAX_PEAKS, num_peaks))
        path = Path(record.file_path)
        y, sr = load_mono(path, target_sr=DEFAULT_SR)
        if y is None or y.size == 0:
            peaks: List[float] = []
            num_samples = 0
        else:
            peaks = compute_peaks_minmax(y, num_peaks)
            num_samples = int(y.size)
        return {
            "music_id": music_id,
            "duration_sec": float(record.duration_sec),
            "sample_rate": int(sr),
            "channels": 1,
            "peaks": peaks,
            "num_peaks": len(peaks),
            "num_samples": num_samples,
        }


_service: Optional[MusicService] = None


def get_music_service() -> MusicService:
    global _service
    if _service is None:
        _service = MusicService()
    return _service
