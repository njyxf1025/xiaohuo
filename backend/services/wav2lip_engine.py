from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np

from core import onnx_provider
from core.config import get_settings
from core.logging import get_logger
from core.onnx_provider import DirectMLNotAvailable
from utils.mel import EXPECTED_CHUNK_FRAMES

_logger = get_logger("services.wav2lip_engine")


class Wav2LipEngineError(RuntimeError):
    pass


class Wav2LipModelNotLoaded(Wav2LipEngineError):
    def __init__(self, message: str = "Wav2Lip model weights are not loaded") -> None:
        super().__init__(message)
        self.code = "model_not_loaded"


class Wav2LipDirectMLNotAvailable(Wav2LipEngineError):
    code = "directml_unavailable"

    def __init__(self, message: str = None) -> None:
        if message is None:
            message = (
                "DirectML execution provider is required but not available. "
                "Install onnxruntime-directml and ensure a DirectML-capable GPU is present. "
                "CPU fallback has been disabled because inference would be unusable."
            )
        super().__init__(message)
        self.code = "directml_unavailable"


@dataclass
class Wav2LipPaths:
    models_dir: Path
    wav2lip_path: Optional[Path]
    face_detect_path: Optional[Path]

    def is_complete(self) -> bool:
        return (
            self.wav2lip_path is not None
            and self.face_detect_path is not None
            and self.wav2lip_path.exists()
            and self.face_detect_path.exists()
        )


ProgressCallback = Callable[[str, float, Optional[str]], None]


DEFAULT_FACE_SIZE = 96
DEFAULT_PAD_BOTTOM_RATIO = 0.10
DEFAULT_FPS = 25
DEFAULT_MEL_CHUNK = EXPECTED_CHUNK_FRAMES
DEFAULT_RESIZE_FACTOR = 1.0
FACE_SCORE_THRESHOLD = 0.3
MEL_HOP = 200
MEL_SR = 16000


def _try_import_ort():
    try:
        import onnxruntime as ort
        return ort
    except Exception as exc:
        _logger.warning("onnxruntime import failed: %s", exc)
        return None


def _try_import_cv2():
    try:
        import cv2
        return cv2
    except Exception as exc:
        _logger.warning("opencv import failed: %s", exc)
        return None


def _build_session_options(ort) -> object:
    try:
        session_options = ort.SessionOptions()
        session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        return session_options
    except Exception as exc:
        _logger.warning(
            "failed to build sequential SessionOptions, falling back to defaults: %s",
            exc,
            extra={"stage": "wav2lip.session_options"},
        )
        try:
            return ort.SessionOptions()
        except Exception as inner_exc:
            _logger.warning(
                "ort.SessionOptions() unavailable: %s", inner_exc,
                extra={"stage": "wav2lip.session_options"},
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


class Wav2LipEngine:
    _instance: Optional["Wav2LipEngine"] = None
    _class_lock = threading.Lock()

    def __init__(self) -> None:
        self._session_lock = threading.Lock()
        self._wav2lip_session = None
        self._face_session = None
        self._providers: List[str] = []
        self._provider_label: str = "-"
        self._paths: Optional[Wav2LipPaths] = None
        self._last_error: Optional[str] = None
        self._wav2lip_path: Optional[str] = None
        self._face_path: Optional[str] = None
        self._mel_input_name: Optional[str] = None
        self._face_input_name: Optional[str] = None

    @classmethod
    def instance(cls) -> "Wav2LipEngine":
        with cls._class_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def is_loaded(self) -> bool:
        return self._wav2lip_session is not None and self._face_session is not None

    def is_directml_ready(self) -> Tuple[bool, str]:
        try:
            return onnx_provider.is_directml_available()
        except Exception as exc:
            return (False, f"directml probe failed: {exc}")

    def provider_label(self) -> str:
        return self._provider_label

    def providers(self) -> List[str]:
        return list(self._providers)

    def last_error(self) -> Optional[str]:
        return self._last_error

    def model_paths(self) -> Optional[Wav2LipPaths]:
        return self._paths

    def warmup(self) -> bool:
        start = time.perf_counter()
        with self._session_lock:
            if self.is_loaded():
                return True
            ort = _try_import_ort()
            if ort is None:
                self._last_error = "onnxruntime not importable"
                _logger.warning(
                    "Wav2Lip warmup skipped: onnxruntime unavailable",
                    extra={"stage": "wav2lip.warmup"},
                )
                return False
            paths = self._discover_model_paths()
            if paths is None or not paths.is_complete():
                self._last_error = "weights missing or incomplete"
                _logger.warning(
                    "Wav2Lip warmup skipped: weights missing wav2lip=%s face=%s",
                    None if paths is None else paths.wav2lip_path,
                    None if paths is None else paths.face_detect_path,
                    extra={"stage": "wav2lip.warmup"},
                )
                return False
            self._paths = paths
            try:
                providers, label = onnx_provider.select_providers()
            except DirectMLNotAvailable as exc:
                self._last_error = f"directml_unavailable: {exc}"
                _logger.error(
                    "Wav2Lip warmup aborted: DirectML unavailable (%s)",
                    exc,
                    extra={"stage": "wav2lip.warmup", "error_code": "directml_unavailable"},
                )
                return False
            if "DmlExecutionProvider" not in providers:
                self._last_error = "selected providers do not include DirectML; refusing CPU fallback"
                _logger.error(
                    "Wav2Lip warmup aborted: providers=%s lacks DirectML",
                    providers,
                    extra={"stage": "wav2lip.warmup", "error_code": "directml_unavailable"},
                )
                return False
            self._providers = list(providers)
            self._provider_label = label
            session_options = _build_session_options(ort)
            if session_options is not None:
                _logger.info(
                    "Wav2Lip session configured with ORT_SEQUENTIAL execution mode (DirectML safe)",
                    extra={
                        "stage": "wav2lip.session_options",
                        "providers": self._providers,
                        "provider_label": self._provider_label,
                    },
                )
            try:
                self._wav2lip_session = _create_inference_session(
                    ort, str(paths.wav2lip_path), list(providers), session_options,
                )
            except Exception as exc:
                self._last_error = f"wav2lip session failed: {exc}"
                _logger.exception("wav2lip session create failed: %s", exc)
                self._wav2lip_session = None
                return False
            try:
                self._face_session = _create_inference_session(
                    ort, str(paths.face_detect_path), list(providers), session_options,
                )
            except Exception as exc:
                self._last_error = f"face session failed: {exc}"
                _logger.exception("face session create failed: %s", exc)
                self._wav2lip_session = None
                self._face_session = None
                return False
            self._resolve_input_names()
            self._wav2lip_path = str(paths.wav2lip_path)
            self._face_path = str(paths.face_detect_path)
        duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
        _logger.info(
            "Wav2Lip warmup ok",
            extra={
                "stage": "wav2lip.warmup",
                "duration_ms": duration_ms,
                "providers": self._providers,
                "provider_label": self._provider_label,
                "wav2lip_path": self._wav2lip_path,
                "face_path": self._face_path,
            },
        )
        return True

    def _resolve_input_names(self) -> None:
        try:
            if self._wav2lip_session is not None:
                for inp in self._wav2lip_session.get_inputs():
                    n = inp.name.lower()
                    if "mel" in n or "audio" in n:
                        self._mel_input_name = inp.name
                    else:
                        self._face_input_name = inp.name
                if self._mel_input_name is None or self._face_input_name is None:
                    names = [inp.name for inp in self._wav2lip_session.get_inputs()]
                    if len(names) >= 1:
                        self._mel_input_name = self._mel_input_name or names[0]
                    if len(names) >= 2:
                        self._face_input_name = self._face_input_name or names[1]
        except Exception as exc:
            _logger.warning("resolve_input_names failed: %s", exc)

    def _discover_model_paths(self) -> Optional[Wav2LipPaths]:
        settings = get_settings()
        models_dir = settings.resolved_models_dir()
        candidates = [
            models_dir / "wav2lip",
            Path("/workspace/models/wav2lip"),
        ]
        wav2lip_path: Optional[Path] = None
        face_path: Optional[Path] = None
        for d in candidates:
            if not d.exists():
                continue
            for name in ("wav2lip.onnx", "wav2lip_hq.onnx", "wav2lip_96.onnx", "wav2lip_gen.onnx"):
                p = d / name
                if p.exists():
                    wav2lip_path = p
                    break
            for name in ("face_detection.onnx", "s3fd.onnx"):
                p = d / name
                if p.exists():
                    face_path = p
                    break
            if wav2lip_path is not None and face_path is not None:
                break
        if wav2lip_path is None and face_path is None:
            return None
        return Wav2LipPaths(
            models_dir=models_dir,
            wav2lip_path=wav2lip_path,
            face_detect_path=face_path,
        )

    def _face_box_from_s3fd(
        self,
        frame: np.ndarray,
        cv2,
    ) -> Optional[Tuple[int, int, int, int]]:
        if self._face_session is None:
            return None
        try:
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if frame.ndim == 3 else frame
            h, w = img.shape[:2]
            target = 640
            scale = min(target / float(h), target / float(w))
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
            resized = cv2.resize(img, (new_w, new_h))
            arr = resized.astype(np.float32) / 255.0
            arr = (arr - 0.5) / 0.5
            chw = np.transpose(arr, (2, 0, 1))[None, ...]
            inputs = self._face_session.get_inputs()
            feed = {inputs[0].name: chw.astype(np.float32)}
            outs = self._face_session.run(None, feed)
            if not outs:
                return None
            out = np.asarray(outs[0])
            if out.size == 0:
                return None
            if out.ndim == 3 and out.shape[0] == 1:
                out = out[0]
            if out.ndim != 2 or out.shape[0] == 0:
                return None
            if out.shape[1] >= 5:
                cx = out[:, 0]
                cy = out[:, 1]
                bw = out[:, 2]
                bh = out[:, 3]
                scores = out[:, 4]
            else:
                cx = out[:, 0]
                cy = out[:, 1]
                bw = out[:, 2]
                bh = out[:, 3]
                scores = out[:, 0]
            if scores is None or scores.size == 0:
                return None
            best_idx = int(np.argmax(scores))
            score = float(scores[best_idx])
            if score < FACE_SCORE_THRESHOLD:
                return None
            x1 = (float(cx[best_idx]) - float(bw[best_idx]) / 2.0) / scale
            y1 = (float(cy[best_idx]) - float(bh[best_idx]) / 2.0) / scale
            x2 = (float(cx[best_idx]) + float(bw[best_idx]) / 2.0) / scale
            y2 = (float(cy[best_idx]) + float(bh[best_idx]) / 2.0) / scale
            ix1 = max(0, int(round(x1)))
            iy1 = max(0, int(round(y1)))
            ix2 = min(w, int(round(x2)))
            iy2 = min(h, int(round(y2)))
            bw_i = max(1, ix2 - ix1)
            bh_i = max(1, iy2 - iy1)
            return (ix1, iy1, bw_i, bh_i)
        except Exception as exc:
            _logger.warning("s3fd inference failed: %s", exc)
            return None

    def _face_box_from_dnn(
        self,
        frame: np.ndarray,
    ) -> Optional[Tuple[int, int, int, int]]:
        try:
            from services.face_detect import FaceDetector, best_face_box
        except Exception as exc:
            _logger.debug("face_detect import failed: %s", exc)
            return None
        try:
            _, boxes = FaceDetector.instance().detect_image(frame)
            best = best_face_box(boxes)
            if best is None:
                return None
            return (int(best.x), int(best.y), int(best.w), int(best.h))
        except Exception as exc:
            _logger.warning("dnn detector failed: %s", exc)
            return None

    @staticmethod
    def _expand_square_box(
        box: Tuple[int, int, int, int],
        frame_shape: Tuple[int, int],
    ) -> Tuple[int, int, int, int]:
        x, y, w, h = box
        H, W = frame_shape[:2]
        side = max(int(w), int(h))
        cx = x + w // 2
        cy = y + h // 2
        x0 = max(0, cx - side // 2)
        y0 = max(0, cy - side // 2)
        x1 = min(W, x0 + side)
        y1 = min(H, y0 + side)
        x0 = max(0, x1 - side)
        y0 = max(0, y1 - side)
        return (x0, y0, x1 - x0, y1 - y0)

    @staticmethod
    def _pad_box(
        box: Tuple[int, int, int, int],
        frame_shape: Tuple[int, int],
        bottom_ratio: float = DEFAULT_PAD_BOTTOM_RATIO,
    ) -> Tuple[int, int, int, int]:
        x, y, w, h = box
        H, W = frame_shape[:2]
        pad_w = int(w * 0.10)
        pad_top = int(h * 0.10)
        pad_bot = int(h * (0.10 + bottom_ratio))
        x0 = max(0, x - pad_w)
        y0 = max(0, y - pad_top)
        x1 = min(W, x + w + pad_w)
        y1 = min(H, y + h + pad_bot)
        return (x0, y0, x1 - x0, y1 - y0)

    def _detect_initial_box(
        self,
        frame: np.ndarray,
    ) -> Tuple[int, int, int, int]:
        cv2 = _try_import_cv2()
        box: Optional[Tuple[int, int, int, int]] = None
        if cv2 is not None and self._face_session is not None:
            box = self._face_box_from_s3fd(frame, cv2)
        if box is None:
            box = self._face_box_from_dnn(frame)
        if box is None:
            h, w = frame.shape[:2]
            side = int(min(h, w) * 0.6)
            cx, cy = w // 2, int(h * 0.45)
            box = (max(0, cx - side // 2), max(0, cy - side // 2), side, side)
            _logger.info(
                "fallback face box used (no detector)",
                extra={"stage": "wav2lip.face_detect", "box": list(box)},
            )
        padded = self._pad_box(box, frame.shape[:2])
        squared = self._expand_square_box(padded, frame.shape[:2])
        return squared

    def _prepare_face_tensor(
        self,
        frame: np.ndarray,
        box: Tuple[int, int, int, int],
    ) -> np.ndarray:
        cv2 = _try_import_cv2()
        if cv2 is None:
            raise Wav2LipEngineError("opencv is required for face prep")
        x, y, w, h = box
        crop = frame[y:y + h, x:x + w]
        if crop.size == 0:
            crop = frame
        face_resized = cv2.resize(crop, (DEFAULT_FACE_SIZE, DEFAULT_FACE_SIZE))
        h2 = DEFAULT_FACE_SIZE
        top = int(h2 * 0.32)
        bottom = int(h2 * 0.65)
        mask = np.zeros_like(face_resized)
        mask[top:bottom, :, :] = face_resized[top:bottom, :, :]
        face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
        mask_rgb = cv2.cvtColor(mask, cv2.COLOR_BGR2RGB)
        stacked = np.concatenate([face_rgb, mask_rgb], axis=-1)
        chw = np.transpose(stacked, (2, 0, 1)).astype(np.float32) / 255.0
        return chw

    def _infer_face(
        self,
        face_chw: np.ndarray,
        mel_chunk: np.ndarray,
    ) -> np.ndarray:
        if self._wav2lip_session is None:
            raise Wav2LipModelNotLoaded()
        face_in = face_chw.astype(np.float32)[None, ...]
        mel_in = mel_chunk.astype(np.float32)[None, ...]
        feed: dict = {}
        if self._mel_input_name:
            feed[self._mel_input_name] = mel_in
        if self._face_input_name:
            feed[self._face_input_name] = face_in
        if not feed:
            inputs = self._wav2lip_session.get_inputs()
            if len(inputs) >= 1:
                feed[inputs[0].name] = mel_in
            if len(inputs) >= 2:
                feed[inputs[1].name] = face_in
        outputs = self._wav2lip_session.run(None, feed)
        if not outputs:
            raise Wav2LipEngineError("wav2lip session returned no output")
        out = np.asarray(outputs[0])
        if out.ndim == 4:
            out = out[0]
        if out.ndim == 3 and out.shape[0] == 6:
            out = out[3:6]
        if out.ndim == 3 and out.shape[-1] == 3:
            out = np.transpose(out, (1, 2, 0))
        out = np.clip(out, 0.0, 1.0)
        out = (out * 255.0).astype(np.uint8)
        return out

    def generate(
        self,
        video_frames: Sequence[np.ndarray],
        audio_mel: np.ndarray,
        progress_cb: Optional[ProgressCallback] = None,
        fps: int = DEFAULT_FPS,
        output_path: Optional[Path] = None,
        resize_factor: float = DEFAULT_RESIZE_FACTOR,
    ) -> np.ndarray:
        if not self.is_loaded():
            try:
                ok = self.warmup()
            except DirectMLNotAvailable as exc:
                raise Wav2LipDirectMLNotAvailable(str(exc)) from exc
            if not ok or not self.is_loaded():
                last = self.last_error() or "unknown"
                if "directml" in last.lower():
                    raise Wav2LipDirectMLNotAvailable(last)
                raise Wav2LipModelNotLoaded(
                    f"wav2lip weights not loaded: {last}"
                )
        if video_frames is None or len(video_frames) == 0:
            raise Wav2LipEngineError("video_frames is empty")
        cv2 = _try_import_cv2()
        if cv2 is None:
            raise Wav2LipEngineError("opencv-python is required for generation")
        if resize_factor is None or resize_factor <= 0:
            resize_factor = 1.0
        try:
            resize_factor = float(resize_factor)
        except (TypeError, ValueError):
            resize_factor = 1.0
        if audio_mel is None:
            raise Wav2LipEngineError("audio_mel is None")
        mel = np.asarray(audio_mel, dtype=np.float32)
        if mel.ndim == 3 and mel.shape[0] == 1:
            mel = mel[0]
        if mel.ndim == 1:
            mel = mel.reshape(-1, 1).T
        n_mels = int(mel.shape[0])
        n_mel_t = int(mel.shape[-1])
        if n_mels <= 0 or n_mel_t <= 0:
            raise Wav2LipEngineError("audio_mel has empty dimensions")

        first = np.asarray(video_frames[0], dtype=np.uint8)
        if first.ndim == 2:
            first = cv2.cvtColor(first, cv2.COLOR_GRAY2BGR)
        if first.shape[-1] == 4:
            first = cv2.cvtColor(first, cv2.COLOR_BGRA2BGR)
        box = self._detect_initial_box(first)
        if progress_cb is not None:
            progress_cb("face_detected", 5.0, f"face box: {list(box)}")

        h, w = first.shape[:2]
        writer = None
        if output_path is not None:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(
                    str(output_path),
                    fourcc,
                    float(fps),
                    (int(w * resize_factor), int(h * resize_factor)),
                )
                if not writer.isOpened():
                    writer = None
            except Exception as exc:
                _logger.warning("VideoWriter init failed: %s", exc)
                writer = None

        out_frames: List[np.ndarray] = []
        samples_per_frame = max(1, int(MEL_SR / max(1, int(fps))))
        mel_per_frame = max(1, int(round(samples_per_frame / float(MEL_HOP))))
        chunk = DEFAULT_MEL_CHUNK
        total = len(video_frames)
        log_step = max(1, total // 20)
        for idx, fr in enumerate(video_frames):
            frame = np.asarray(fr, dtype=np.uint8)
            if frame.ndim == 2:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            if frame.shape[-1] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            if frame.shape[:2] != (h, w):
                frame = cv2.resize(frame, (w, h))
            x, y, bw, bh = box
            x2 = min(w, x + bw)
            y2 = min(h, y + bh)
            roi_w = max(1, x2 - x)
            roi_h = max(1, y2 - y)
            face_chw = self._prepare_face_tensor(frame, (x, y, roi_w, roi_h))
            mel_block_start = (idx // mel_per_frame) * chunk
            if mel_block_start + chunk <= n_mel_t:
                mel_chunk = mel[:, mel_block_start:mel_block_start + chunk]
            else:
                if n_mel_t >= chunk:
                    mel_chunk = mel[:, n_mel_t - chunk:n_mel_t]
                else:
                    pad = chunk - n_mel_t
                    mel_chunk = np.pad(mel, ((0, 0), (0, pad)), mode="edge")
                    mel_chunk = mel_chunk[:, :chunk]
            try:
                pred = self._infer_face(face_chw, mel_chunk)
            except Exception as exc:
                _logger.exception("wav2lip inference failed on frame %d: %s", idx, exc)
                pred = cv2.cvtColor(face_chw[:3].transpose(1, 2, 0), cv2.COLOR_RGB2BGR)
            if pred.shape[:2] != (roi_h, roi_w):
                pred = cv2.resize(pred, (roi_w, roi_h))
            try:
                pred_bgr = cv2.cvtColor(pred, cv2.COLOR_RGB2BGR)
            except Exception:
                pred_bgr = pred
            out = frame.copy()
            mask = np.zeros((roi_h, roi_w), dtype=np.float32)
            top = int(roi_h * 0.32)
            mask[top:, :] = 1.0
            mask_3 = np.stack([mask] * 3, axis=-1)
            roi = out[y:y + roi_h, x:x + roi_w].astype(np.float32)
            blended = pred_bgr.astype(np.float32) * mask_3 + roi * (1.0 - mask_3)
            out[y:y + roi_h, x:x + roi_w] = np.clip(blended, 0, 255).astype(np.uint8)
            if resize_factor != 1.0:
                out = cv2.resize(
                    out,
                    (int(w * resize_factor), int(h * resize_factor)),
                    interpolation=cv2.INTER_AREA if resize_factor < 1.0 else cv2.INTER_CUBIC,
                )
            out_frames.append(out)
            if writer is not None:
                writer.write(out)
            if progress_cb is not None and (idx % log_step == 0 or idx == total - 1):
                pct = 10.0 + 80.0 * (float(idx + 1) / float(max(1, total)))
                progress_cb("frame_inferred", pct, f"frame {idx + 1}/{total}")
        if writer is not None:
            writer.release()
        if progress_cb is not None:
            progress_cb("frames_written", 95.0, f"wrote {len(out_frames)} frames")
        if out_frames:
            stacked_arr = np.stack(out_frames, axis=0)
        else:
            stacked_arr = np.zeros((0, h, w, 3), dtype=np.uint8)
        if progress_cb is not None:
            progress_cb("done", 100.0, f"generated {len(out_frames)} frames")
        return stacked_arr
