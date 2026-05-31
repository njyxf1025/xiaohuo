import time
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes.music_router import router as music_router
from app.core.config import settings
from app.core.logger import logger, new_request_id, set_request_id
from app.api.routes.gpu_router import router as gpu_router
from app.api.routes.avatar_router import router as avatar_router
from app.api.routes.generate_router import router as generate_router

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

app.include_router(gpu_router)
app.include_router(avatar_router)
app.include_router(music_router)
app.include_router(generate_router)

settings.AVATAR_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/data/avatars", StaticFiles(directory=str(settings.AVATAR_DIR)), name="avatars")

settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/data/output", StaticFiles(directory=str(settings.OUTPUT_DIR)), name="output")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    rid = new_request_id()
    start = time.time()
    logger.info(f"请求开始 {request.method} {request.url.path}")
    response = await call_next(request)
    duration = time.time() - start
    logger.info(
        f"请求完成 {request.method} {request.url.path} "
        f"status={response.status_code} duration={duration:.3f}s"
    )
    response.headers["X-Request-ID"] = rid
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"未处理异常 {request.method} {request.url.path}: {exc}\n"
        f"{traceback.format_exc()}"
    )
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"},
    )


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
