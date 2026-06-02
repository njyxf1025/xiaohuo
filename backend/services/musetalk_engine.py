from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

import numpy as np

from core import torch_provider
from core.config import get_settings
from core.logging import get_logger
from core.torch_provider import TorchDirectMLNotAvailable, is_torch_directml_available

_logger = get_logger("services.musetalk_engine")

ProgressCallback = Optional[Callable[[str, float, Optional[str]], None]]


class MuseTalkEngineError(RuntimeError):
    pass


class MuseTalkDirectMLNotAvailable(MuseTalkEngineError):
    code = "directml_unavailable"

    def __init__(self, message: str = None) -> None:
        if message is None:
            message = (
                "MuseTalk requires torch-directml. Install torch-directml and ensure a "
                "DirectML-capable GPU is present. CPU fallback has been disabled because "
                "PyTorch CPU inference is unusable for real-time lip-sync."
            )
        super().__init__(message)
        self.code = "directml_unavailable"


class MuseTalkModelNotLoaded(MuseTalkEngineError):
    def __init__(self, message: str = "MuseTalk model weights are not loaded") -> None:
        super().__init__(message)
        self.code = "model_not_loaded"


class MuseTalkNotImplemented(MuseTalkEngineError):
    code = "not_implemented"

    def __init__(self, message: str = None) -> None:
        if message is None:
            message = (
                "MuseTalk inference is reserved for the step-2 rollout. "
                "The engine skeleton is in place (singleton, DirectML check, "
                "weight discovery, progress callback) but the actual inference "
                "graph is not yet implemented. Until step 2 lands, use Wav2Lip-ONNX."
            )
        super().__init__(message)
        self.code = "not_implemented"


DEFAULT_CANDIDATE_NAMES: Tuple[str, ...] = (
    "musetalk.safetensors",
    "musetalk.onnx",
    "musetalk.pt",
    "musetalk.pth",
    "MuseTalk.safetensors",
    "MuseTalk.pt",
    "musetalk_fp16.safetensors",
    "musetalk_fp32.safetensors",
)


@dataclass
class MuseTalkPaths:
    model_path: Optional[Path]
    config_path: Optional[Path]
    hubert_path: Optional[Path]

    def is_complete(self) -> bool:
        return self.model_path is not None and self.model_path.exists()


class MuseTalkEngine:
    _instance: Optional["MuseTalkEngine"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._model = None
        self._model_lock = threading.Lock()
        self._device: Optional[Any] = None
        self._device_id: int = 0
        self._providers: List[str] = []
        self._provider_label: str = "unloaded"
        self._last_error: Optional[str] = None
        self._paths: Optional[MuseTalkPaths] = None
        self._loaded = False
        self._torch = None

    @classmethod
    def instance(cls) -> "MuseTalkEngine":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = MuseTalkEngine()
            return cls._instance

    def is_loaded(self) -> bool:
        return self._loaded and self._model is not None

    def is_directml_ready(self) -> Tuple[bool, str]:
        return is_torch_directml_available()

    def last_error(self) -> Optional[str]:
        return self._last_error

    def providers(self) -> List[str]:
        return list(self._providers)

    def provider_label(self) -> str:
        return self._provider_label

    def device_id(self) -> int:
        return self._device_id

    def model_paths(self) -> Optional[MuseTalkPaths]:
        return self._paths

    def _discover_paths(self) -> MuseTalkPaths:
        settings = get_settings()
        roots: List[Path] = []
        env_root = os.getenv("MUSETALK_DIR")
        if env_root:
            roots.append(Path(env_root))
        try:
            roots.append(Path(settings.models_dir) / "musetalk")
        except Exception:
            pass
        roots.append(Path("/workspace/models/musetalk"))

        seen: set = set()
        model_path: Optional[Path] = None
        for root in roots:
            try:
                if not root.exists():
                    continue
            except Exception:
                continue
            if root in seen:
                continue
            seen.add(root)
            for name in DEFAULT_CANDIDATE_NAMES:
                p = root / name
                if p.exists():
                    model_path = p
                    break
            if model_path is not None:
                break
        config_candidates: List[Path] = []
        for root in roots:
            config_candidates.append(root / "config.yaml")
            config_candidates.append(root / "musetalk.json")
        config_path = next((p for p in config_candidates if p.exists()), None)
        hubert_candidates: List[Path] = []
        for root in roots:
            hubert_candidates.append(root / "hubert.pt")
            hubert_candidates.append(root / "chinese-hubert.pt")
            hubert_candidates.append(root / "hubert_base.pt")
        hubert_path = next((p for p in hubert_candidates if p.exists()), None)
        return MuseTalkPaths(
            model_path=model_path,
            config_path=config_path,
            hubert_path=hubert_path,
        )

    def warmup(self) -> bool:
        with self._model_lock:
            if self.is_loaded():
                return True
            try:
                import torch
            except Exception as exc:
                self._last_error = f"torch import failed: {exc}"
                _logger.error(
                    "muse warmup aborted: torch not importable (%s)", exc,
                    extra={"stage": "musetalk.warmup", "error_code": "torch_unavailable"},
                )
                return False
            self._torch = torch
            try:
                dml_ok, dml_reason = is_torch_directml_available()
            except Exception as exc:
                self._last_error = f"directml probe failed: {exc}"
                _logger.error(
                    "muse warmup aborted: probe crashed (%s)", exc,
                    extra={"stage": "musetalk.warmup", "error_code": "directml_unavailable"},
                )
                return False
            if not dml_ok:
                self._last_error = f"directml_unavailable: {dml_reason}"
                _logger.error(
                    "muse warmup aborted: %s", dml_reason,
                    extra={
                        "stage": "musetalk.warmup",
                        "error_code": "directml_unavailable",
                        "reason": dml_reason,
                    },
                )
                return False
            try:
                self._device = torch_provider.get_torch_directml_device(0)
            except TorchDirectMLNotAvailable as exc:
                self._last_error = f"directml_unavailable: {exc}"
                _logger.error(
                    "muse warmup aborted: %s", exc,
                    extra={"stage": "musetalk.warmup", "error_code": "directml_unavailable"},
                )
                return False
            self._device_id = 0
            self._providers = ["torch-directml"]
            self._provider_label = "torch-directml"
            paths = self._discover_paths()
            self._paths = paths
            if paths.model_path is None:
                self._last_error = (
                    "MuseTalk weights not found under models/musetalk/. "
                    "Engine is ready on DirectML but inference will fail with MuseTalkNotImplemented "
                    "until the step-2 rollout. Wav2Lip-ONNX is fully functional."
                )
                _logger.warning(
                    "muse warmup: DirectML ready, weights missing — engine stays in skeleton mode",
                    extra={
                        "stage": "musetalk.warmup",
                        "providers": self._providers,
                        "model_path": None,
                    },
                )
                self._loaded = True
                return True
            try:
                self._model = self._load_model_stub(paths.model_path)
            except Exception as exc:
                self._last_error = f"muse model load failed: {exc}"
                _logger.exception("muse model load failed: %s", exc)
                self._model = None
                self._loaded = False
                return False
            self._loaded = True
            _logger.info(
                "muse engine ready (skeleton, weights present but inference not yet implemented)",
                extra={
                    "stage": "musetalk.warmup",
                    "providers": self._providers,
                    "device": str(self._device),
                    "model_path": str(paths.model_path),
                },
            )
            return True

    def _load_model_stub(self, model_path: Path) -> dict:
        return {
            "path": str(model_path),
            "kind": "stub",
            "loaded_at": time.time(),
        }

    def generate(
        self,
        video_frames: List[np.ndarray],
        audio_features: np.ndarray,
        progress_cb: ProgressCallback = None,
        fps: int = 25,
        output_path: Optional[Path] = None,
        resize_factor: float = 1.0,
    ) -> np.ndarray:
        if not self.is_loaded():
            try:
                ok = self.warmup()
            except (MuseTalkDirectMLNotAvailable, TorchDirectMLNotAvailable) as exc:
                raise MuseTalkDirectMLNotAvailable(str(exc)) from exc
            if not ok or not self.is_loaded():
                last = self.last_error() or "unknown"
                if "directml" in last.lower() or "torch" in last.lower():
                    raise MuseTalkDirectMLNotAvailable(last)
                raise MuseTalkModelNotLoaded(
                    f"muse weights not loaded: {last}"
                )
        if self._paths is None or self._paths.model_path is None:
            if progress_cb is not None:
                progress_cb("muse.not_implemented", 0.0, "muse weights not present")
            raise MuseTalkNotImplemented()
        if progress_cb is not None:
            progress_cb(
                "muse.not_implemented", 0.0,
                "MuseTalk inference graph is the step-2 deliverable; Wav2Lip-ONNX is the active engine.",
            )
        raise MuseTalkNotImplemented()


def get_musetalk_engine() -> MuseTalkEngine:
    return MuseTalkEngine.instance()
