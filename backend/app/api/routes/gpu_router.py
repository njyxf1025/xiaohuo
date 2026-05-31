from __future__ import annotations

from fastapi import APIRouter

from app.core.gpu import GPUManager

router = APIRouter(prefix="/api/gpu", tags=["GPU"])


@router.get("/info")
async def gpu_info():
    manager = GPUManager.get_instance()
    return manager.get_device_info()


@router.get("/memory")
async def gpu_memory():
    manager = GPUManager.get_instance()
    memory = manager.get_memory_info()
    if memory is None:
        return {"available": False, "detail": "CPU 模式无 GPU 内存信息"}
    return {"available": True, **memory}
