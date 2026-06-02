from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence

import numpy as np

from core.logging import get_logger
from services.vocal_separation import (
    VocalSeparationDirectMLNotAvailable,
    VocalSeparationError,
    VocalSeparationModelNotLoaded,
    get_vocal_separator,
)
from services.wav2lip_engine import (
    DEFAULT_FPS,
    DEFAULT_RESIZE_FACTOR,
    Wav2LipDirectMLNotAvailable,
    Wav2LipEngine,
    Wav2LipEngineError,
    Wav2LipModelNotLoaded,
)
from utils.ffmpeg import mux_audio_video, probe_ffmpeg
from utils.mel import compute_mel

_logger = get_logger("services.wav2lip_pipeline")


MEL_SAMPLE_RATE = 16000


ProgressCallback = Callable[[str, float, Optional[str]], None]


@dataclass
class PipelineRequest:
    audio_path: Path
    avatar_path: Path
    avatar_kind: str
    slice_start: float
    slice_end: float
    output_path: Path
    thumbnail_path: Optional[Path] = None
    fps: int = DEFAULT_FPS
    resize_factor: float = DEFAULT_RESIZE_FACTOR
    progress_cb: Optional[ProgressCallback] = None
    preserve_audio: bool = True
    enable_vocal_separation: bool = True

    def duration_sec(self) -> float:
        s = float(self.slice_start)
        e = float(self.slice_end)
        return max(0.0, e - s)


@dataclass
class PipelineResult:
    output_path: Path
    thumbnail_path: Optional[Path]
    duration_sec: float
    num_frames: int
    fps: int
    width: int
    height: int
    mel_shape: tuple
    muxed: bool
    vocal_separation_applied: bool
    vocals_path: Optional[Path] = None
    accompaniment_path: Optional[Path] = None


def _try_import_cv2():
    try:
        import cv2
        return cv2
    except Exception as exc:
        _logger.warning("opencv import failed: %s", exc)
        return None


def _try_import_sf():
    try:
        import soundfile as sf
        return sf
    except Exception as exc:
        _logger.warning("soundfile import failed: %s", exc)
        return None


def _try_import_librosa():
    try:
        import librosa
        return librosa
    except Exception as exc:
        _logger.warning("librosa import failed: %s", exc)
        return None


def _load_audio_mono(path: Path, target_sr: int = MEL_SAMPLE_RATE):
    sf = _try_import_sf()
    if sf is not None:
        try:
            data, sr = sf.read(str(path), always_2d=False, dtype="float32")
            if hasattr(data, "ndim") and data.ndim > 1:
                data = np.mean(data, axis=-1)
            data = np.asarray(data, dtype=np.float32).reshape(-1)
            if int(sr) != int(target_sr):
                librosa = _try_import_librosa()
                if librosa is not None:
                    data = librosa.resample(
                        data, orig_sr=int(sr), target_sr=int(target_sr), res_type="kaiser_fast"
                    )
                else:
                    ratio = float(target_sr) / float(sr) if sr > 0 else 1.0
                    n_new = max(1, int(round(data.shape[-1] * ratio)))
                    data = np.interp(
                        np.linspace(0.0, 1.0, n_new, dtype=np.float32),
                        np.linspace(0.0, 1.0, data.shape[-1], dtype=np.float32),
                        data,
                    ).astype(np.float32)
            return np.asarray(data, dtype=np.float32), int(target_sr)
        except Exception as exc:
            _logger.warning("soundfile load failed for %s: %s", path, exc)
    librosa = _try_import_librosa()
    if librosa is not None:
        try:
            y, sr = librosa.load(str(path), sr=target_sr, mono=True)
            return np.asarray(y, dtype=np.float32), int(sr)
        except Exception as exc:
            _logger.exception("librosa load failed for %s: %s", path, exc)
    raise RuntimeError("no audio backend available (soundfile + librosa both unavailable)")


def _slice_audio(
    samples: np.ndarray,
    sample_rate: int,
    start_sec: float,
    end_sec: float,
) -> np.ndarray:
    if samples is None or samples.size == 0 or sample_rate <= 0:
        return np.zeros((0,), dtype=np.float32)
    if end_sec <= start_sec:
        return np.zeros((0,), dtype=np.float32)
    start_idx = max(0, int(start_sec * sample_rate))
    end_idx = min(samples.shape[-1], int(end_sec * sample_rate))
    if end_idx <= start_idx:
        return np.zeros((0,), dtype=np.float32)
    return np.asarray(samples[start_idx:end_idx], dtype=np.float32)


def _load_image_frames(path: Path, num_frames: int) -> List[np.ndarray]:
    cv2 = _try_import_cv2()
    if cv2 is None:
        raise RuntimeError("opencv required to load image avatar")
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        try:
            from PIL import Image
        except Exception:
            raise RuntimeError(f"failed to read image: {path}")
        pil = Image.open(str(path)).convert("RGB")
        arr = np.asarray(pil, dtype=np.uint8)
        arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        img = arr
    if img is None or img.size == 0:
        raise RuntimeError(f"failed to decode image: {path}")
    return [img.copy() for _ in range(max(1, int(num_frames)))]


def _load_video_frames(path: Path, max_frames: Optional[int] = None) -> List[np.ndarray]:
    cv2 = _try_import_cv2()
    if cv2 is None:
        raise RuntimeError("opencv required to load video avatar")
    cap = cv2.VideoCapture(str(path))
    if cap is None or not cap.isOpened():
        raise RuntimeError(f"failed to open video: {path}")
    frames: List[np.ndarray] = []
    try:
        while True:
            ok, fr = cap.read()
            if not ok or fr is None:
                break
            frames.append(fr)
            if max_frames is not None and len(frames) >= int(max_frames):
                break
    finally:
        cap.release()
    if not frames:
        raise RuntimeError(f"video contained no decodable frames: {path}")
    return frames


def _write_thumbnail(frame: np.ndarray, target: Path, size: int = 256) -> Path:
    cv2 = _try_import_cv2()
    if cv2 is None:
        return target
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    h, w = frame.shape[:2]
    if w <= 0 or h <= 0:
        return target
    scale = min(float(size) / float(w), float(size) / float(h))
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
    canvas = np.full((size, size, 3), 255, dtype=resized.dtype)
    x_off = (size - new_w) // 2
    y_off = (size - new_h) // 2
    canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized
    try:
        cv2.imwrite(str(target), canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    except Exception as exc:
        _logger.warning("thumbnail write failed: %s", exc)
    return target


def run_pipeline(req: PipelineRequest) -> PipelineResult:
    engine = Wav2LipEngine.instance()
    start = time.perf_counter()
    audio_path = Path(req.audio_path)
    avatar_path = Path(req.avatar_path)
    output_path = Path(req.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if req.thumbnail_path is not None:
        thumb_target = Path(req.thumbnail_path)
    else:
        thumb_target = output_path.with_suffix(".jpg")
    thumb_target.parent.mkdir(parents=True, exist_ok=True)
    if not audio_path.exists():
        raise FileNotFoundError(f"audio not found: {audio_path}")
    if not avatar_path.exists():
        raise FileNotFoundError(f"avatar not found: {avatar_path}")

    if req.progress_cb is not None:
        req.progress_cb("load_audio", 1.0, f"loading {audio_path.name}")

    samples, sr = _load_audio_mono(audio_path, target_sr=MEL_SAMPLE_RATE)
    sliced = _slice_audio(samples, sr, float(req.slice_start), float(req.slice_end))
    if sliced.size == 0:
        raise ValueError("audio slice is empty (invalid range)")

    vocals_path: Optional[Path] = None
    accompaniment_path: Optional[Path] = None
    vocal_separation_applied = False
    audio_for_mel: np.ndarray = sliced
    audio_for_mux: np.ndarray = sliced
    if req.enable_vocal_separation:
        separator = get_vocal_separator()
        if req.progress_cb is not None:
            req.progress_cb(
                "vocal_separation", 2.0,
                "separating vocals from accompaniment (DirectML)",
            )
        try:
            sep_dir = output_path.parent / "_vocal_separation"
            try:
                vocals_audio_path, acc_audio_path = separator.separate(
                    str(audio_path), str(sep_dir), progress_cb=req.progress_cb,
                )
            except VocalSeparationDirectMLNotAvailable as exc:
                raise
            except VocalSeparationModelNotLoaded as exc:
                _logger.warning(
                    "vocal_separation model not loaded (%s); using original audio as vocals, "
                    "no accompaniment to re-mix (lipsync may jitter on heavy bass)",
                    exc,
                    extra={"stage": "wav2lip.vocal_separation_fallback"},
                )
            except VocalSeparationError as exc:
                _logger.warning(
                    "vocal_separation failed (%s); falling back to original audio",
                    exc,
                    extra={"stage": "wav2lip.vocal_separation_fallback"},
                )
            else:
                vocals_path = Path(vocals_audio_path)
                accompaniment_path = Path(acc_audio_path) if acc_audio_path else None
                v_samples, v_sr = _load_audio_mono(vocals_path, target_sr=MEL_SAMPLE_RATE)
                v_sliced = _slice_audio(
                    v_samples, v_sr, float(req.slice_start), float(req.slice_end)
                )
                if v_sliced.size > 0:
                    audio_for_mel = v_sliced
                    audio_for_mux = v_sliced
                    vocal_separation_applied = True
                    _logger.info(
                        "vocal_separation applied; Wav2Lip will use vocals track, "
                        "final video will re-mix accompaniment",
                        extra={
                            "stage": "wav2lip.vocal_separation_applied",
                            "vocals_path": str(vocals_path),
                            "accompaniment_path": (
                                str(accompaniment_path) if accompaniment_path else None
                            ),
                        },
                    )
                else:
                    _logger.warning(
                        "vocal_separation produced empty vocals slice; "
                        "falling back to original audio"
                    )
        except VocalSeparationDirectMLNotAvailable:
            raise

    if req.progress_cb is not None:
        req.progress_cb("mel_compute", 4.0, f"mel on {audio_for_mel.shape[-1]} samples")
    mel = compute_mel(audio_for_mel, sample_rate=sr)
    if mel.ndim != 2 or mel.size == 0:
        raise Wav2LipEngineError("mel-spectrogram produced empty result")

    duration_sec = float(audio_for_mel.shape[-1]) / float(sr) if sr > 0 else 0.0
    fps = max(1, int(req.fps or DEFAULT_FPS))
    n_video_frames = max(1, int(round(duration_sec * float(fps))))

    if req.progress_cb is not None:
        req.progress_cb("load_avatar", 5.0, f"loading {avatar_path.name} ({req.avatar_kind})")
    if req.avatar_kind == "image":
        frames = _load_image_frames(avatar_path, num_frames=n_video_frames)
    elif req.avatar_kind == "video":
        frames = _load_video_frames(avatar_path, max_frames=n_video_frames)
    else:
        raise ValueError(f"unsupported avatar_kind: {req.avatar_kind}")
    if len(frames) == 0:
        raise RuntimeError("avatar produced no frames")
    if len(frames) < n_video_frames:
        last = frames[-1]
        while len(frames) < n_video_frames:
            frames.append(last.copy())
    elif len(frames) > n_video_frames:
        frames = frames[:n_video_frames]

    if req.progress_cb is not None:
        req.progress_cb("warmup", 7.0, "warming Wav2Lip engine")
    if not engine.is_loaded():
        try:
            ok = engine.warmup()
        except Wav2LipDirectMLNotAvailable as exc:
            raise
        if not ok or not engine.is_loaded():
            last = engine.last_error() or "unknown"
            if "directml" in last.lower():
                raise Wav2LipDirectMLNotAvailable(last)
            raise Wav2LipModelNotLoaded(
                f"wav2lip weights not loaded: {last}"
            )

    def _cb(stage: str, percent: float, message: Optional[str] = None) -> None:
        if req.progress_cb is not None:
            mapped = 7.0 + 0.85 * float(percent)
            req.progress_cb(stage, mapped, message)

    try:
        out_arr = engine.generate(
            video_frames=frames,
            audio_mel=mel,
            progress_cb=_cb,
            fps=fps,
            output_path=output_path,
            resize_factor=float(req.resize_factor or DEFAULT_RESIZE_FACTOR),
        )
    except Wav2LipModelNotLoaded:
        raise
    except Wav2LipEngineError:
        raise
    except Exception as exc:
        _logger.exception("engine.generate crashed: %s", exc)
        raise Wav2LipEngineError(f"engine generate failed: {exc}")

    if out_arr is None or out_arr.size == 0:
        raise Wav2LipEngineError("engine produced no frames")

    first_frame = out_arr[0] if out_arr.ndim == 4 else out_arr
    try:
        _write_thumbnail(first_frame, thumb_target, size=256)
    except Exception as exc:
        _logger.warning("thumbnail generation failed: %s", exc)

    muxed = False
    mux_audio: Optional[np.ndarray] = None
    mux_sr: int = sr
    if vocal_separation_applied and accompaniment_path is not None:
        try:
            acc_samples, acc_sr = _load_audio_mono(
                accompaniment_path, target_sr=MEL_SAMPLE_RATE
            )
            acc_sliced = _slice_audio(
                acc_samples, acc_sr, float(req.slice_start), float(req.slice_end)
            )
            if acc_sliced.size > 0:
                mux_audio = acc_sliced
                mux_sr = acc_sr
                _logger.info(
                    "using separated accompaniment for final remux "
                    "(vocals drive lipsync, user hears full song minus vocals)",
                    extra={"stage": "wav2lip.mux_accompaniment"},
                )
        except Exception as exc:
            _logger.warning("accompaniment load failed, falling back to vocals for mux: %s", exc)
    if mux_audio is None and req.preserve_audio:
        mux_audio = audio_for_mux
        mux_sr = sr

    if mux_audio is not None and mux_audio.size > 0:
        tmp_audio = output_path.with_suffix(".tmp.wav")
        try:
            sf = _try_import_sf()
            if sf is not None:
                sf.write(str(tmp_audio), mux_audio, mux_sr, subtype="PCM_16")
                if probe_ffmpeg():
                    muxed = mux_audio_video(output_path, tmp_audio, output_path)
                else:
                    _logger.warning(
                        "ffmpeg unavailable, video written without audio: %s",
                        output_path,
                    )
            else:
                _logger.warning("soundfile unavailable, video written without audio")
        except Exception as exc:
            _logger.warning("audio mux step failed: %s", exc)
        finally:
            try:
                if tmp_audio.exists():
                    tmp_audio.unlink()
            except Exception:
                pass

    elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
    h, w = (out_arr.shape[1], out_arr.shape[2]) if out_arr.ndim == 4 else (0, 0)
    _logger.info(
        "wav2lip pipeline finished",
        extra={
            "stage": "wav2lip.pipeline",
            "duration_ms": elapsed_ms,
            "num_frames": int(out_arr.shape[0]) if out_arr.ndim == 4 else 0,
            "fps": fps,
            "width": w,
            "height": h,
            "muxed": muxed,
            "vocal_separation_applied": vocal_separation_applied,
            "output": str(output_path),
        },
    )
    return PipelineResult(
        output_path=output_path,
        thumbnail_path=thumb_target if thumb_target.exists() else None,
        duration_sec=duration_sec,
        num_frames=int(out_arr.shape[0]) if out_arr.ndim == 4 else 0,
        fps=fps,
        width=w,
        height=h,
        mel_shape=(int(mel.shape[0]), int(mel.shape[-1])),
        muxed=muxed,
        vocal_separation_applied=vocal_separation_applied,
        vocals_path=vocals_path,
        accompaniment_path=accompaniment_path,
    )
