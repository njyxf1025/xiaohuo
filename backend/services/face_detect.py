from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from core.logging import get_logger

_logger = get_logger("services.face_detect")


@dataclass
class FaceBox:
    x: int
    y: int
    w: int
    h: int

    def as_list(self) -> List[int]:
        return [int(self.x), int(self.y), int(self.w), int(self.h)]


DetectorKind = str


class FaceDetector:
    _instance: "Optional[FaceDetector]" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._dnn = None
        self._dnn_kind: DetectorKind = "none"
        self._haar = None
        self._init_lock = threading.Lock()
        self._initialized = False
        self._last_error: Optional[str] = None

    @classmethod
    def instance(cls) -> "FaceDetector":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def kind(self) -> DetectorKind:
        self._ensure_initialized()
        if self._dnn is not None:
            return self._dnn_kind
        if self._haar is not None:
            return "haar"
        return "none"

    def last_error(self) -> Optional[str]:
        return self._last_error

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            self._try_init_dnn()
            if self._dnn is None:
                self._try_init_haar()
            if self._dnn is None and self._haar is None:
                _logger.warning(
                    "no face detector available; face checks will return has_face=None",
                    extra={"stage": "face_detect.init"},
                )
            else:
                _logger.info(
                    "face detector initialized",
                    extra={"stage": "face_detect.init", "kind": self.kind()},
                )
            self._initialized = True

    def _try_init_dnn(self) -> None:
        try:
            import cv2
        except Exception as exc:
            _logger.debug("cv2 import failed for DNN: %s", exc)
            return

        prototxt_candidates = self._dnn_prototxt_candidates()
        weights_candidates = self._dnn_weights_candidates()
        prototxt = next((p for p in prototxt_candidates if p.exists()), None)
        weights = next((p for p in weights_candidates if p.exists()), None)

        if prototxt is not None and weights is not None:
            try:
                net = cv2.dnn.readNetFromCaffe(str(prototxt), str(weights))
                self._dnn = net
                self._dnn_kind = "caffe"
                _logger.info(
                    "loaded Caffe DNN face detector",
                    extra={
                        "stage": "face_detect.dnn",
                        "prototxt": str(prototxt),
                        "weights": str(weights),
                    },
                )
                return
            except Exception as exc:
                self._last_error = f"caffe load failed: {exc}"
                _logger.warning("caffe dnn load failed: %s", exc)
        else:
            _logger.debug(
                "caffemodel not bundled; prototxt=%s weights=%s",
                prototxt,
                weights,
            )

        onnx_candidates = self._dnn_onnx_candidates()
        onnx_path = next((p for p in onnx_candidates if p.exists()), None)
        if onnx_path is not None:
            try:
                net = cv2.dnn.readNetFromONNX(str(onnx_path))
                self._dnn = net
                self._dnn_kind = "onnx"
                _logger.info(
                    "loaded ONNX face detector",
                    extra={"stage": "face_detect.dnn", "model": str(onnx_path)},
                )
                return
            except Exception as exc:
                self._last_error = f"onnx load failed: {exc}"
                _logger.warning("onnx dnn load failed: %s", exc)

    def _try_init_haar(self) -> None:
        try:
            import cv2
        except Exception as exc:
            self._last_error = f"cv2 import failed: {exc}"
            _logger.warning("cv2 import failed: %s", exc)
            return
        try:
            haar_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
            if not haar_path.exists():
                _logger.warning("haar xml missing: %s", haar_path)
                return
            clf = cv2.CascadeClassifier(str(haar_path))
            if clf.empty():
                _logger.warning("haar classifier empty: %s", haar_path)
                return
            self._haar = clf
            _logger.info("loaded haar cascade", extra={"stage": "face_detect.haar"})
        except Exception as exc:
            self._last_error = f"haar init failed: {exc}"
            _logger.warning("haar init failed: %s", exc)

    def _dnn_prototxt_candidates(self) -> List[Path]:
        root = Path(__file__).resolve().parent.parent
        return [
            root / "models" / "face_detector" / "deploy.prototxt",
            root / "data" / "avatars" / "models" / "deploy.prototxt",
            Path("/workspace/models/face_detector/deploy.prototxt"),
        ]

    def _dnn_weights_candidates(self) -> List[Path]:
        root = Path(__file__).resolve().parent.parent
        return [
            root / "models" / "face_detector" / "res10_300x300_ssd_iter_140000.caffemodel",
            root / "data" / "avatars" / "models" / "res10_300x300_ssd_iter_140000.caffemodel",
            Path("/workspace/models/face_detector/res10_300x300_ssd_iter_140000.caffemodel"),
        ]

    def _dnn_onnx_candidates(self) -> List[Path]:
        root = Path(__file__).resolve().parent.parent
        return [
            root / "models" / "face_detector" / "s3fd.onnx",
            root / "models" / "wav2lip" / "face_detection.onnx",
            root / "data" / "avatars" / "models" / "s3fd.onnx",
            Path("/workspace/models/face_detector/s3fd.onnx"),
        ]

    def detect(
        self,
        image_path: Path,
        *,
        confidence: float = 0.5,
        min_size: int = 60,
    ) -> Tuple[Optional[bool], List[FaceBox]]:
        self._ensure_initialized()
        try:
            import cv2
        except Exception as exc:
            self._last_error = f"cv2 import failed: {exc}"
            _logger.warning("cv2 unavailable during detect: %s", exc)
            return None, []

        try:
            img = cv2.imread(str(image_path))
        except Exception as exc:
            _logger.warning("imread failed for %s: %s", image_path, exc)
            return None, []
        if img is None:
            _logger.warning("imread returned None for %s", image_path)
            return None, []

        return self.detect_image(img, confidence=confidence, min_size=min_size)

    def detect_image(
        self,
        img,
        *,
        confidence: float = 0.5,
        min_size: int = 60,
    ) -> Tuple[Optional[bool], List[FaceBox]]:
        boxes: List[FaceBox] = []
        kind = self.kind()
        if kind == "none":
            return None, []
        if kind in ("caffe", "onnx"):
            boxes = self._detect_dnn(img, confidence=confidence)
        elif kind == "haar":
            boxes = self._detect_haar(img, min_size=min_size)
        has_face = len(boxes) > 0
        return has_face, boxes

    def _detect_dnn(self, img, *, confidence: float) -> List[FaceBox]:
        boxes: List[FaceBox] = []
        try:
            import cv2

            (h, w) = img.shape[:2]
            blob = cv2.dnn.blobFromImage(
                cv2.resize(img, (300, 300)),
                1.0,
                (300, 300),
                (104.0, 177.0, 123.0),
            )
            assert self._dnn is not None
            self._dnn.setInput(blob)
            detections = self._dnn.forward()
            if detections is None:
                return boxes
            for i in range(detections.shape[2]):
                c = float(detections[0, 0, i, 2])
                if c < confidence:
                    continue
                box = detections[0, 0, i, 3:7] * [w, h, w, h]
                (x1, y1, x2, y2) = box.astype("int")
                x1 = max(0, int(x1))
                y1 = max(0, int(y1))
                x2 = min(w, int(x2))
                y2 = min(h, int(y2))
                bw = max(0, x2 - x1)
                bh = max(0, y2 - y1)
                if bw <= 0 or bh <= 0:
                    continue
                boxes.append(FaceBox(x=x1, y=y1, w=bw, h=bh))
        except Exception as exc:
            _logger.warning("dnn detect failed: %s", exc)
            self._last_error = f"dnn detect error: {exc}"
        return boxes

    def _detect_haar(self, img, *, min_size: int) -> List[FaceBox]:
        boxes: List[FaceBox] = []
        try:
            import cv2

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            assert self._haar is not None
            rects = self._haar.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(int(min_size), int(min_size)),
                flags=cv2.CASCADE_SCALE_IMAGE,
            )
            if rects is None:
                return boxes
            for (x, y, w, h) in rects:
                if w <= 0 or h <= 0:
                    continue
                boxes.append(FaceBox(x=int(x), y=int(y), w=int(w), h=int(h)))
        except Exception as exc:
            _logger.warning("haar detect failed: %s", exc)
            self._last_error = f"haar detect error: {exc}"
        return boxes


def detect_face_in_image(image_path: Path) -> Tuple[Optional[bool], List[FaceBox]]:
    return FaceDetector.instance().detect(image_path)


def best_face_box(boxes: List[FaceBox]) -> Optional[FaceBox]:
    if not boxes:
        return None
    return max(boxes, key=lambda b: b.w * b.h)
