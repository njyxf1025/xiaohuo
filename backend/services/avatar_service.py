from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import get_settings
from core.logging import get_logger
from services.face_detect import FaceBox, FaceDetector, best_face_box
from utils import files as file_utils
from utils.id_gen import new_id

_logger = get_logger("services.avatar_service")

IMAGE_EXTS = ("jpg", "jpeg", "png", "webp")
VIDEO_EXTS = ("mp4", "mov")

IMAGE_MIME_HINTS = (
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "application/octet-stream",
)
VIDEO_MIME_HINTS = (
    "video/mp4",
    "video/quicktime",
    "video/x-quicktime",
    "video/mov",
    "application/octet-stream",
)

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024
THUMBNAIL_SIZE = 256
PRESET_THUMBNAIL_SIZE = 512
PRESET_VIDEO_FRAME_BUDGET = 60

PRESET_PALETTE = (
    ("Preset 01", (64, 128, 200)),
    ("Preset 02", (200, 96, 96)),
    ("Preset 03", (96, 180, 120)),
)
PRESETS_BUNDLE_DIR = Path(__file__).resolve().parent.parent / "data" / "avatars" / "presets"


@dataclass
class AvatarRecord:
    avatar_id: str
    type: str
    filename: str
    extension: str
    file_path: str
    thumbnail_path: str
    mime_type: Optional[str] = None
    size_bytes: int = 0
    face_box: Optional[List[int]] = None
    has_face: Optional[bool] = None
    created_at: float = field(default_factory=lambda: time.time())
    is_preset: bool = False
    display_name: Optional[str] = None
    description: Optional[str] = None

    def to_metadata_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("file_path", None)
        d.pop("thumbnail_path", None)
        d.pop("mime_type", None)
        d.pop("display_name", None)
        return d


@dataclass
class PresetAvatarRecord:
    preset_id: str
    name: str
    filename: str
    file_path: str
    thumbnail_path: str
    description: Optional[str] = None
    created_at: float = field(default_factory=lambda: time.time())


class AvatarService:
    def __init__(self) -> None:
        self._avatars: Dict[str, AvatarRecord] = {}
        self._presets: Dict[str, PresetAvatarRecord] = {}
        self._lock = threading.RLock()
        self._presets_loaded = False
        self._bootstrap_dirs()
        self._load_registry()
        self._load_presets_from_disk()

    @property
    def base_dir(self) -> Path:
        return _avatars_base_dir()

    @property
    def uploads_dir(self) -> Path:
        d = self.base_dir / "uploads"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def thumbs_dir(self) -> Path:
        d = self.base_dir / "thumbs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def presets_dir(self) -> Path:
        d = PRESETS_BUNDLE_DIR
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def registry_path(self) -> Path:
        return self.base_dir / "registry.json"

    def _bootstrap_dirs(self) -> None:
        for d in (self.base_dir, self.uploads_dir, self.thumbs_dir, self.presets_dir):
            d.mkdir(parents=True, exist_ok=True)

    def _load_registry(self) -> None:
        path = self.registry_path
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as exc:
            _logger.warning("registry load failed: %s", exc)
            return
        items = payload.get("avatars") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return
        loaded = 0
        for raw in items:
            if not isinstance(raw, dict):
                continue
            try:
                rec = AvatarRecord(
                    avatar_id=str(raw.get("avatar_id") or ""),
                    type=str(raw.get("type") or "image"),
                    filename=str(raw.get("filename") or ""),
                    extension=str(raw.get("extension") or ""),
                    file_path=str(raw.get("file_path") or ""),
                    thumbnail_path=str(raw.get("thumbnail_path") or ""),
                    mime_type=raw.get("mime_type"),
                    size_bytes=int(raw.get("size_bytes") or 0),
                    face_box=list(raw["face_box"]) if raw.get("face_box") else None,
                    has_face=raw.get("has_face"),
                    created_at=float(raw.get("created_at") or 0.0),
                    is_preset=bool(raw.get("is_preset") or False),
                    display_name=raw.get("display_name"),
                    description=raw.get("description"),
                )
            except Exception as exc:
                _logger.warning("registry entry skipped: %s", exc)
                continue
            if not rec.avatar_id:
                continue
            if not Path(rec.file_path).exists() or not Path(rec.thumbnail_path).exists():
                continue
            with self._lock:
                self._avatars[rec.avatar_id] = rec
            loaded += 1
        if loaded:
            _logger.info(
                "registry restored",
                extra={"stage": "avatar.registry", "count": loaded},
            )

    def _save_registry(self) -> None:
        path = self.registry_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            payload = {
                "version": 1,
                "updated_at": time.time(),
                "avatars": [r.to_metadata_dict() | {
                    "file_path": r.file_path,
                    "thumbnail_path": r.thumbnail_path,
                    "mime_type": r.mime_type,
                    "display_name": r.display_name,
                } for r in self._avatars.values()],
            }
        try:
            tmp = path.with_suffix(path.suffix + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            tmp.replace(path)
        except Exception as exc:
            _logger.exception("registry save failed: %s", exc)

    @staticmethod
    def is_image_extension(ext: str) -> bool:
        return (ext or "").lower().lstrip(".") in IMAGE_EXTS

    @staticmethod
    def is_video_extension(ext: str) -> bool:
        return (ext or "").lower().lstrip(".") in VIDEO_EXTS

    @staticmethod
    def resolve_kind(ext: str, content_type: Optional[str]) -> Optional[str]:
        e = (ext or "").lower().lstrip(".")
        if AvatarService.is_image_extension(e):
            return "image"
        if AvatarService.is_video_extension(e):
            return "video"
        if content_type:
            ct = content_type.lower()
            if ct.startswith("image/"):
                return "image"
            if ct.startswith("video/"):
                return "video"
        return None

    @staticmethod
    def extension_from_mime(content_type: Optional[str]) -> str:
        ct = (content_type or "").lower()
        if "jpeg" in ct or "jpg" in ct:
            return "jpg"
        if "png" in ct:
            return "png"
        if "webp" in ct:
            return "webp"
        if "quicktime" in ct or ct.endswith("/mov"):
            return "mov"
        if "mp4" in ct:
            return "mp4"
        return ""

    @staticmethod
    def mime_is_image(content_type: Optional[str]) -> bool:
        if not content_type:
            return False
        ct = content_type.lower()
        if ct.startswith("image/"):
            return True
        return any(h in ct for h in IMAGE_MIME_HINTS if h != "application/octet-stream")

    @staticmethod
    def mime_is_video(content_type: Optional[str]) -> bool:
        if not content_type:
            return False
        ct = content_type.lower()
        if ct.startswith("video/"):
            return True
        return any(h in ct for h in VIDEO_MIME_HINTS if h != "application/octet-stream")

    def list_avatars(self) -> List[AvatarRecord]:
        with self._lock:
            return sorted(
                self._avatars.values(),
                key=lambda r: float(r.created_at),
                reverse=True,
            )

    def get_avatar(self, avatar_id: str) -> Optional[AvatarRecord]:
        with self._lock:
            return self._avatars.get(avatar_id)

    def delete_avatar(self, avatar_id: str) -> bool:
        with self._lock:
            rec = self._avatars.get(avatar_id)
        if rec is None:
            return False
        if rec.is_preset:
            raise ValueError("preset avatars cannot be deleted")
        for path_str in (rec.file_path, rec.thumbnail_path):
            try:
                p = Path(path_str)
                if p.exists():
                    p.unlink()
            except Exception as exc:
                _logger.warning("failed to remove %s: %s", path_str, exc)
        with self._lock:
            self._avatars.pop(avatar_id, None)
        self._save_registry()
        return True

    async def upload(
        self,
        filename: str,
        content_type: Optional[str],
        data: bytes,
    ) -> AvatarRecord:
        _, ext = file_utils.split_ext(filename or "")
        if not ext:
            ext = self.extension_from_mime(content_type)
        ext = (ext or "").lower().lstrip(".")
        kind = self.resolve_kind(ext, content_type)
        if kind is None:
            raise ValueError(f"unsupported file extension: .{ext}")
        if kind == "image":
            if len(data) > MAX_IMAGE_BYTES:
                raise ValueError(
                    f"image too large: {len(data)} bytes (max {MAX_IMAGE_BYTES})"
                )
        elif kind == "video":
            if len(data) > MAX_VIDEO_BYTES:
                raise ValueError(
                    f"video too large: {len(data)} bytes (max {MAX_VIDEO_BYTES})"
                )

        avatar_id = new_id(prefix="avt_", length=12)
        target_ext = ext if ext else ("jpg" if kind == "image" else "mp4")
        target_name = f"{avatar_id}.{target_ext}"
        target_path = self.uploads_dir / target_name
        await file_utils.write_bytes_async(target_path, data)

        thumb_path = self.thumbs_dir / f"{avatar_id}.jpg"
        face_box: Optional[FaceBox] = None
        has_face: Optional[bool] = None

        if kind == "image":
            ok, has_face, face_box = self._process_image(target_path, thumb_path)
        else:
            ok, has_face, face_box = self._process_video(target_path, thumb_path)

        if not ok:
            try:
                if target_path.exists():
                    target_path.unlink()
            except Exception:
                pass
            raise ValueError(
                "could not locate a face in the uploaded media "
                "(image too small, blurry, or profile / non-frontal)"
            )

        record = AvatarRecord(
            avatar_id=avatar_id,
            type=kind,
            filename=file_utils.safe_basename(filename) or target_name,
            extension=target_ext,
            file_path=str(target_path),
            thumbnail_path=str(thumb_path),
            mime_type=content_type,
            size_bytes=len(data),
            face_box=face_box.as_list() if face_box is not None else None,
            has_face=has_face,
            created_at=time.time(),
            is_preset=False,
        )
        with self._lock:
            self._avatars[avatar_id] = record
        self._save_registry()
        return record

    def _process_image(
        self,
        src_path: Path,
        thumb_path: Path,
    ) -> Tuple[bool, Optional[bool], Optional[FaceBox]]:
        try:
            import cv2
        except Exception as exc:
            _logger.warning("cv2 import failed during image processing: %s", exc)
            return self._process_image_fallback(src_path, thumb_path)

        try:
            img = cv2.imread(str(src_path))
        except Exception as exc:
            _logger.warning("cv2.imread failed for %s: %s", src_path, exc)
            img = None
        if img is None:
            return self._process_image_fallback(src_path, thumb_path)

        has_face, boxes = FaceDetector.instance().detect_image(img)
        box = best_face_box(boxes)
        try:
            self._write_jpg_thumbnail(img, thumb_path, size=THUMBNAIL_SIZE)
        except Exception as exc:
            _logger.warning("cv2 thumbnail write failed: %s", exc)
            return False, has_face, box
        if has_face is False:
            return False, has_face, box
        return True, has_face, box

    def _process_image_fallback(
        self,
        src_path: Path,
        thumb_path: Path,
    ) -> Tuple[bool, Optional[bool], Optional[FaceBox]]:
        try:
            from PIL import Image
        except Exception as exc:
            _logger.warning("PIL unavailable for image fallback: %s", exc)
            return False, None, None
        try:
            with Image.open(str(src_path)) as im:
                im = im.convert("RGB")
                im.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
                im.save(str(thumb_path), format="JPEG", quality=88)
        except Exception as exc:
            _logger.warning("PIL thumbnail write failed: %s", exc)
            return False, None, None
        return True, None, None

    def _process_video(
        self,
        src_path: Path,
        thumb_path: Path,
    ) -> Tuple[bool, Optional[bool], Optional[FaceBox]]:
        try:
            import cv2
        except Exception as exc:
            _logger.warning("cv2 import failed during video processing: %s", exc)
            return False, None, None
        cap = None
        try:
            cap = cv2.VideoCapture(str(src_path))
        except Exception as exc:
            _logger.warning("VideoCapture open failed: %s", exc)
            return False, None, None
        if cap is None or not cap.isOpened():
            _logger.warning("video open failed: %s", src_path)
            if cap is not None:
                cap.release()
            return False, None, None

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        duration = (frame_count / fps) if fps > 0 else 0.0
        sample_budget = PRESET_VIDEO_FRAME_BUDGET
        step = max(1, frame_count // sample_budget) if frame_count > 0 else 1

        best_img = None
        best_box: Optional[FaceBox] = None
        best_has_face: Optional[bool] = None
        index = 0
        sampled = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok or frame is None:
                    break
                if index % step == 0:
                    sampled += 1
                    has_face, boxes = FaceDetector.instance().detect_image(frame)
                    box = best_face_box(boxes)
                    if has_face is True and box is not None:
                        best_img = frame
                        best_box = box
                        best_has_face = True
                        break
                    if has_face is None and best_img is None:
                        best_img = frame
                        best_box = None
                        best_has_face = None
                index += 1
                if sampled >= sample_budget * 2:
                    break
        except Exception as exc:
            _logger.warning("video frame read failed: %s", exc)
        finally:
            cap.release()

        if best_img is None:
            _logger.warning(
                "no decodable frame extracted from video (duration=%.2fs, frames=%d)",
                duration,
                frame_count,
            )
            return False, None, None

        try:
            self._write_jpg_thumbnail(best_img, thumb_path, size=THUMBNAIL_SIZE)
        except Exception as exc:
            _logger.warning("video thumbnail write failed: %s", exc)
            return False, best_has_face, best_box
        if best_has_face is False:
            return False, best_has_face, best_box
        return True, best_has_face, best_box

    @staticmethod
    def _write_jpg_thumbnail(img, thumb_path: Path, *, size: int) -> None:
        import cv2
        import numpy as np

        if img is None:
            raise ValueError("img is None")
        h, w = img.shape[:2]
        if w <= 0 or h <= 0:
            raise ValueError("invalid image shape")
        scale = min(float(size) / float(w), float(size) / float(h))
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        canvas = np.full((size, size, 3), 255, dtype=resized.dtype)
        x_off = (size - new_w) // 2
        y_off = (size - new_h) // 2
        canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(thumb_path), canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 90])

    def _load_presets_from_disk(self) -> None:
        with self._lock:
            if self._presets_loaded:
                return
        manifest = self.presets_dir / "manifest.json"
        if not manifest.exists():
            self._ensure_presets()
        try:
            with open(manifest, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as exc:
            _logger.warning("preset manifest load failed: %s", exc)
            self._presets_loaded = True
            return
        items = payload.get("presets") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            self._presets_loaded = True
            return
        for raw in items:
            if not isinstance(raw, dict):
                continue
            try:
                rec = PresetAvatarRecord(
                    preset_id=str(raw.get("preset_id") or ""),
                    name=str(raw.get("name") or "Preset"),
                    filename=str(raw.get("filename") or ""),
                    file_path=str(raw.get("file_path") or ""),
                    thumbnail_path=str(raw.get("thumbnail_path") or ""),
                    description=raw.get("description"),
                    created_at=float(raw.get("created_at") or 0.0),
                )
            except Exception as exc:
                _logger.warning("preset entry skipped: %s", exc)
                continue
            if not rec.preset_id or not rec.filename:
                continue
            file_p = Path(rec.file_path)
            thumb_p = Path(rec.thumbnail_path)
            if not file_p.exists() or not thumb_p.exists():
                continue
            with self._lock:
                self._presets[rec.preset_id] = rec
        self._presets_loaded = True
        _logger.info(
            "presets loaded",
            extra={"stage": "avatar.presets", "count": len(self._presets)},
        )

    def _ensure_presets(self) -> None:
        manifest = self.presets_dir / "manifest.json"
        if manifest.exists():
            return
        self._generate_placeholder_presets()

    def _generate_placeholder_presets(self) -> None:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except Exception as exc:
            _logger.warning("PIL unavailable; cannot generate placeholder presets: %s", exc)
            self._write_empty_manifest()
            return

        manifests: List[Dict[str, Any]] = []
        now = time.time()
        for idx, (name, color) in enumerate(PRESET_PALETTE):
            preset_id = f"preset_{idx + 1:02d}"
            filename = f"{preset_id}.png"
            file_path = self.presets_dir / filename
            thumb_path = self.presets_dir / f"{preset_id}_thumb.jpg"
            try:
                self._draw_placeholder(file_path, name, color, PRESET_THUMBNAIL_SIZE)
                self._draw_placeholder_thumb(thumb_path, name, color, 256)
            except Exception as exc:
                _logger.warning("placeholder generation failed for %s: %s", name, exc)
                continue
            rec = PresetAvatarRecord(
                preset_id=preset_id,
                name=name,
                filename=filename,
                file_path=str(file_path),
                thumbnail_path=str(thumb_path),
                description="auto-generated placeholder avatar",
                created_at=now + idx,
            )
            with self._lock:
                self._presets[rec.preset_id] = rec
            manifests.append(
                {
                    "preset_id": rec.preset_id,
                    "name": rec.name,
                    "filename": rec.filename,
                    "file_path": rec.file_path,
                    "thumbnail_path": rec.thumbnail_path,
                    "description": rec.description,
                    "created_at": rec.created_at,
                }
            )
            _logger.info(
                "preset generated",
                extra={"stage": "avatar.presets", "preset_id": preset_id, "preset_name": name},
            )

        if not manifests:
            self._write_empty_manifest()
            return

        manifest = self.presets_dir / "manifest.json"
        try:
            with open(manifest, "w", encoding="utf-8") as f:
                json.dump(
                    {"version": 1, "updated_at": time.time(), "presets": manifests},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            _logger.info(
                "preset manifest written",
                extra={"stage": "avatar.presets", "path": str(manifest), "count": len(manifests)},
            )
        except Exception as exc:
            _logger.exception("preset manifest write failed: %s", exc)

    def _write_empty_manifest(self) -> None:
        manifest = self.presets_dir / "manifest.json"
        try:
            with open(manifest, "w", encoding="utf-8") as f:
                json.dump({"version": 1, "presets": []}, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            _logger.warning("empty preset manifest write failed: %s", exc)

    @staticmethod
    def _draw_placeholder(out_path: Path, name: str, color, size: int) -> None:
        from PIL import Image, ImageDraw, ImageFont

        bg = (int(color[0]), int(color[1]), int(color[2]))
        img = Image.new("RGB", (size, size), bg)
        draw = ImageDraw.Draw(img)
        face_cx, face_cy = size // 2, int(size * 0.45)
        face_r = int(size * 0.22)
        skin = (244, 220, 198)
        draw.ellipse(
            (face_cx - face_r, face_cy - face_r, face_cx + face_r, face_cy + face_r),
            fill=skin,
            outline=(60, 60, 60),
            width=3,
        )
        eye_r = max(4, int(face_r * 0.10))
        eye_dx = int(face_r * 0.40)
        eye_dy = int(face_r * 0.10)
        for sign in (-1, 1):
            cx = face_cx + sign * eye_dx
            cy = face_cy - eye_dy
            draw.ellipse(
                (cx - eye_r, cy - eye_r, cx + eye_r, cy + eye_r),
                fill=(20, 20, 20),
            )
        mouth_w = int(face_r * 0.55)
        mouth_h = int(face_r * 0.18)
        draw.arc(
            (
                face_cx - mouth_w,
                face_cy + int(face_r * 0.10),
                face_cx + mouth_w,
                face_cy + int(face_r * 0.10) + mouth_h * 2,
            ),
            start=20,
            end=160,
            fill=(40, 40, 40),
            width=4,
        )
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        text = name
        if font is not None:
            try:
                tb = draw.textbbox((0, 0), text, font=font)
                tw = tb[2] - tb[0]
                th = tb[3] - tb[1]
                tx = (size - tw) // 2
                ty = int(size * 0.82)
                draw.text((tx, ty), text, fill=(255, 255, 255), font=font)
            except Exception:
                pass
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(out_path), format="PNG")

    @staticmethod
    def _draw_placeholder_thumb(out_path: Path, name: str, color, size: int) -> None:
        from PIL import Image, ImageDraw, ImageFont

        bg = (int(color[0]), int(color[1]), int(color[2]))
        img = Image.new("RGB", (size, size), bg)
        draw = ImageDraw.Draw(img)
        face_cx, face_cy = size // 2, int(size * 0.48)
        face_r = int(size * 0.24)
        skin = (244, 220, 198)
        draw.ellipse(
            (face_cx - face_r, face_cy - face_r, face_cx + face_r, face_cy + face_r),
            fill=skin,
            outline=(60, 60, 60),
            width=2,
        )
        eye_r = max(3, int(face_r * 0.11))
        eye_dx = int(face_r * 0.40)
        eye_dy = int(face_r * 0.10)
        for sign in (-1, 1):
            cx = face_cx + sign * eye_dx
            cy = face_cy - eye_dy
            draw.ellipse(
                (cx - eye_r, cy - eye_r, cx + eye_r, cy + eye_r),
                fill=(20, 20, 20),
            )
        draw.arc(
            (
                face_cx - int(face_r * 0.55),
                face_cy + int(face_r * 0.10),
                face_cx + int(face_r * 0.55),
                face_cy + int(face_r * 0.10) + int(face_r * 0.36),
            ),
            start=20,
            end=160,
            fill=(40, 40, 40),
            width=3,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(out_path), format="JPEG", quality=88)

    def list_presets(self) -> List[PresetAvatarRecord]:
        with self._lock:
            if not self._presets_loaded:
                self._load_presets_from_disk()
            return list(self._presets.values())

    def get_preset(self, preset_id: str) -> Optional[PresetAvatarRecord]:
        with self._lock:
            return self._presets.get(preset_id)

    def preset_thumbnail_path(self, preset_id: str) -> Optional[Path]:
        rec = self.get_preset(preset_id)
        if rec is None:
            return None
        p = Path(rec.thumbnail_path)
        return p if p.exists() else None

    def preset_file_path(self, preset_id: str) -> Optional[Path]:
        rec = self.get_preset(preset_id)
        if rec is None:
            return None
        p = Path(rec.file_path)
        return p if p.exists() else None


def _avatars_base_dir() -> Path:
    settings = get_settings()
    base = settings.resolved_data_dir() / "avatars"
    base.mkdir(parents=True, exist_ok=True)
    return base


_service: Optional[AvatarService] = None
_service_lock = threading.Lock()


def get_avatar_service() -> AvatarService:
    global _service
    with _service_lock:
        if _service is None:
            _service = AvatarService()
        return _service
