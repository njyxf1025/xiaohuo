from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.logging import get_logger
from models.generation_schemas import TaskState
from utils.id_gen import new_id

_logger = get_logger("services.task_manager")


@dataclass
class TaskRecord:
    task_id: str
    status: TaskState
    progress: float = 0.0
    stage: str = "-"
    message: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    model: str = "wav2lip"
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())
    request_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, TaskState) else str(self.status)
        return d


ProgressCallback = Callable[[str, float, Optional[str]], None]


class TaskManager:
    _instance: Optional["TaskManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._tasks: Dict[str, TaskRecord] = {}
        self._cancel_flags: Dict[str, threading.Event] = {}
        self._mu = threading.RLock()
        self._max_records = 512

    @classmethod
    def instance(cls) -> "TaskManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _prune_if_needed(self) -> None:
        with self._mu:
            if len(self._tasks) <= self._max_records:
                return
            ordered = sorted(self._tasks.values(), key=lambda r: r.created_at)
            extras = len(self._tasks) - self._max_records
            for rec in ordered[:extras]:
                self._tasks.pop(rec.task_id, None)
                ev = self._cancel_flags.pop(rec.task_id, None)
                if ev is not None:
                    ev.set()

    def create_task(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        task_id: Optional[str] = None,
        model: str = "wav2lip",
    ) -> str:
        tid = task_id or new_id(prefix="gen_", length=14)
        record = TaskRecord(
            task_id=tid,
            status=TaskState.PENDING,
            progress=0.0,
            stage="pending",
            message="task created",
            params=dict(params) if isinstance(params, dict) else None,
            request_id=request_id,
            model=str(model or "wav2lip").lower(),
        )
        with self._mu:
            self._tasks[tid] = record
            self._cancel_flags[tid] = threading.Event()
        self._prune_if_needed()
        _logger.info(
            "task created",
            extra={
                "stage": "task.create",
                "task_id": tid,
                "request_id": request_id or "-",
                "task_model": record.model,
            },
        )
        return tid

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        with self._mu:
            rec = self._tasks.get(task_id)
            return rec

    def list_tasks(self, limit: int = 50) -> List[TaskRecord]:
        with self._mu:
            ordered = sorted(
                self._tasks.values(),
                key=lambda r: r.created_at,
                reverse=True,
            )
            try:
                lim = max(1, min(int(limit), len(ordered)))
            except (TypeError, ValueError):
                lim = min(50, len(ordered))
            return ordered[:lim]

    def update_progress(
        self,
        task_id: str,
        percent: float,
        stage: str,
        message: Optional[str] = None,
    ) -> None:
        try:
            pct = float(percent)
        except (TypeError, ValueError):
            pct = 0.0
        pct = max(0.0, min(100.0, pct))
        with self._mu:
            rec = self._tasks.get(task_id)
            if rec is None:
                return
            if rec.status in (TaskState.SUCCESS, TaskState.FAILED, TaskState.CANCELLED):
                return
            if rec.status == TaskState.PENDING:
                rec.status = TaskState.RUNNING
            rec.progress = pct
            rec.stage = str(stage or "-")
            if message is not None:
                rec.message = str(message)
            rec.updated_at = time.time()

    def complete_task(self, task_id: str, result: Optional[Dict[str, Any]] = None) -> None:
        with self._mu:
            rec = self._tasks.get(task_id)
            if rec is None:
                return
            rec.status = TaskState.SUCCESS
            rec.progress = 100.0
            rec.stage = "completed"
            rec.result = result if isinstance(result, dict) else None
            if result is not None and "message" in result and isinstance(result["message"], str):
                rec.message = result["message"]
            else:
                rec.message = "task completed"
            rec.error = None
            rec.updated_at = time.time()
            ev = self._cancel_flags.get(task_id)
        if ev is not None:
            ev.set()
        _logger.info(
            "task completed",
            extra={"stage": "task.complete", "task_id": task_id},
        )

    def fail_task(self, task_id: str, error: str) -> None:
        with self._mu:
            rec = self._tasks.get(task_id)
            if rec is None:
                return
            rec.status = TaskState.FAILED
            rec.stage = "failed"
            rec.error = str(error)
            rec.message = str(error)
            rec.updated_at = time.time()
            ev = self._cancel_flags.get(task_id)
        if ev is not None:
            ev.set()
        _logger.warning(
            "task failed",
            extra={"stage": "task.fail", "task_id": task_id, "err_message": str(error)},
        )

    def cancel_task(self, task_id: str) -> bool:
        with self._mu:
            rec = self._tasks.get(task_id)
            if rec is None:
                return False
            if rec.status in (TaskState.SUCCESS, TaskState.FAILED, TaskState.CANCELLED):
                return False
            rec.status = TaskState.CANCELLED
            rec.stage = "cancelled"
            rec.message = "cancelled by user"
            rec.updated_at = time.time()
            ev = self._cancel_flags.get(task_id)
        if ev is not None:
            ev.set()
        _logger.info(
            "task cancelled",
            extra={"stage": "task.cancel", "task_id": task_id},
        )
        return True

    def is_cancelled(self, task_id: str) -> bool:
        with self._mu:
            ev = self._cancel_flags.get(task_id)
        if ev is None:
            return False
        return ev.is_set()

    def make_callback(self, task_id: str) -> ProgressCallback:
        def _cb(stage: str, percent: float, message: Optional[str] = None) -> None:
            if self.is_cancelled(task_id):
                raise TaskCancelled(task_id)
            self.update_progress(task_id, percent, stage, message)

        return _cb

    def to_response(self, rec: TaskRecord) -> Dict[str, Any]:
        return {
            "task_id": rec.task_id,
            "status": rec.status.value if isinstance(rec.status, TaskState) else str(rec.status),
            "progress": float(rec.progress),
            "stage": rec.stage or "-",
            "message": rec.message,
            "params": rec.params,
            "result": rec.result,
            "error": rec.error,
            "model": rec.model,
            "created_at": float(rec.created_at),
            "updated_at": float(rec.updated_at),
            "request_id": rec.request_id,
        }


class TaskCancelled(Exception):
    def __init__(self, task_id: str) -> None:
        super().__init__(f"task cancelled: {task_id}")
        self.task_id = task_id


_manager: Optional[TaskManager] = None
_manager_lock = threading.Lock()


def get_task_manager() -> TaskManager:
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = TaskManager.instance()
        return _manager
