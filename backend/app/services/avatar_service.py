from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import cv2
import face_recognition
import numpy as np

from app.core.config import settings
from app.core.logger import logger


def detect_face(image_path: str) -> dict:
    image = face_recognition.load_image_file(image_path)
    face_locations = face_recognition.face_locations(image)
    result: dict = {
        "face_detected": len(face_locations) > 0,
        "face_count": len(face_locations),
        "face_locations": [list(loc) for loc in face_locations],
        "warning": None,
        "error": None,
    }
    if len(face_locations) == 0:
        result["error"] = "未检测到人脸，请上传包含清晰人脸的图片"
    elif len(face_locations) > 1:
        result["warning"] = f"检测到{len(face_locations)}张人脸，建议使用仅包含单张人脸的图片"
    return result


def detect_face_from_video(video_path: str) -> dict:
    cap = cv2.VideoCapture(video_path)
    success, frame = cap.read()
    cap.release()
    if not success:
        return {
            "face_detected": False,
            "face_count": 0,
            "face_locations": [],
            "warning": None,
            "error": "无法读取视频帧",
        }
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_frame)
    result: dict = {
        "face_detected": len(face_locations) > 0,
        "face_count": len(face_locations),
        "face_locations": [list(loc) for loc in face_locations],
        "warning": None,
        "error": None,
    }
    if len(face_locations) == 0:
        result["error"] = "视频第一帧未检测到人脸，请上传包含清晰人脸的视频"
    elif len(face_locations) > 1:
        result["warning"] = f"视频第一帧检测到{len(face_locations)}张人脸，建议使用仅包含单张人脸的视频"
    return result


PRESET_AVATARS = [
    {
        "id": "preset-001",
        "name": "默认形象-小美",
        "preview_url": "/api/avatar/preset-001/preview",
        "image_path": str(settings.MODELS_DIR / "presets" / "preset_001.png"),
    },
    {
        "id": "preset-002",
        "name": "默认形象-小明",
        "preview_url": "/api/avatar/preset-002/preview",
        "image_path": str(settings.MODELS_DIR / "presets" / "preset_002.png"),
    },
    {
        "id": "preset-003",
        "name": "默认形象-小华",
        "preview_url": "/api/avatar/preset-003/preview",
        "image_path": str(settings.MODELS_DIR / "presets" / "preset_003.png"),
    },
]


def get_preset_avatars() -> list[dict]:
    return PRESET_AVATARS


def get_preset_avatar(avatar_id: str) -> dict | None:
    for avatar in PRESET_AVATARS:
        if avatar["id"] == avatar_id:
            return avatar
    return None


_AVATAR_META_FILE = settings.AVATAR_DIR / "avatars_meta.json"


def _load_custom_avatars() -> list[dict]:
    if not _AVATAR_META_FILE.exists():
        return []
    with open(_AVATAR_META_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_custom_avatars(avatars: list[dict]) -> None:
    settings.AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    with open(_AVATAR_META_FILE, "w", encoding="utf-8") as f:
        json.dump(avatars, f, ensure_ascii=False, indent=2)


def save_avatar(file_path: Path, file_type: str, original_filename: str) -> dict:
    avatar_id = str(uuid.uuid4())
    ext = file_path.suffix
    dest_name = f"{avatar_id}{ext}"
    dest_path = settings.AVATAR_DIR / dest_name
    settings.AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file_path, dest_path)

    if file_type.startswith("image"):
        face_result = detect_face(str(dest_path))
    elif file_type.startswith("video"):
        face_result = detect_face_from_video(str(dest_path))
    else:
        face_result = {
            "face_detected": False,
            "face_count": 0,
            "face_locations": [],
            "warning": None,
            "error": "不支持的文件类型",
        }

    avatar_meta = {
        "id": avatar_id,
        "name": original_filename,
        "type": file_type,
        "source": "custom",
        "preview_url": f"/api/avatar/{avatar_id}/preview",
        "file_path": str(dest_path),
        "face_detection": face_result,
    }

    custom_avatars = _load_custom_avatars()
    custom_avatars.append(avatar_meta)
    _save_custom_avatars(custom_avatars)

    logger.info(f"形象上传成功 avatar_id={avatar_id} type={file_type}")
    return avatar_meta


def get_custom_avatar(avatar_id: str) -> dict | None:
    custom_avatars = _load_custom_avatars()
    for avatar in custom_avatars:
        if avatar["id"] == avatar_id:
            return avatar
    return None


def get_all_custom_avatars() -> list[dict]:
    return _load_custom_avatars()


def delete_custom_avatar(avatar_id: str) -> bool:
    custom_avatars = _load_custom_avatars()
    target = None
    remaining = []
    for avatar in custom_avatars:
        if avatar["id"] == avatar_id:
            target = avatar
        else:
            remaining.append(avatar)
    if target is None:
        return False
    file_path = Path(target.get("file_path", ""))
    if file_path.exists():
        file_path.unlink()
    _save_custom_avatars(remaining)
    logger.info(f"形象删除成功 avatar_id={avatar_id}")
    return True
