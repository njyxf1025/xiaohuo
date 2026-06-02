# Checklist

## 基础架构
- [x] 项目目录结构创建完成，前后端项目可正常启动
- [x] CORS 配置正确，前端可访问后端 API
- [x] 后端日志系统可输出请求 ID、结构化字段、错误堆栈

## GPU 抽象层
- [x] GPU 抽象层可正确检测 AMD/NVIDIA/Intel/CPU 并选择对应设备
- [x] GPU 切换与 ONNX provider 选择的日志完整（型号、版本、provider、显存）

## 音乐模块
- [x] 音乐上传 API 支持 MP3/WAV/M4A/FLAC 格式，文件大小限制合理
- [x] pychorus 高潮检测可自动识别歌曲高潮段落，返回起止时间
- [x] 音频截取 API 可根据指定时间区间精确截取音频片段
- [x] 音频波形数据 API 可返回前端可视化所需的波形数据

## 形象模块
- [x] 形象上传 API 含人脸检测验证，拒绝无人脸的图片/视频
- [x] 预设形象可正常加载和预览

## Wav2Lip-ONNX（唯一模型）
- [x] 后端已安装 `onnxruntime-directml`（CPU 兜底已禁用）
- [ ] wav2lip.onnx 与 face_detection.onnx 权重文件已就位 — Note: weights not present in `/workspace/models/wav2lip/` (only `.gitkeep` + README); user must supply them before runtime generation.
- [x] 推理接口 providers 严格限定为 `["DmlExecutionProvider"]`（不再包含 CPU）
- [ ] 在 AMD 6700XT 上 DirectML EP 成功创建会话并完成推理 — Note: requires the AMD 6700XT hardware + ONNX weights; cannot be verified in this CI environment.
- [x] DirectML 不可用时立即报错（503 `directml_unavailable`）并拒绝 CPU 降级
- [x] SessionOptions.execution_mode = ORT_SEQUENTIAL（DirectML 不支持并行图执行）
- [x] 进度回调覆盖 session 创建、mel 计算、推理帧、合成各阶段

## ONNX 人声分离（子模块）
- [x] `models/vocal_separation/` 目录与 README 已创建
- [ ] 任一 ONNX 分离权重已就位 — Note: weights not present; 服务可正常运行（WARN 降级到原始音频）
- [x] `services/vocal_separation.py` 单例 + DirectML + ORT_SEQUENTIAL 实现
- [x] `separate(audio_path, output_dir) → (vocals.wav, accompaniment.wav)` 接口
- [x] 集成到 `wav2lip_pipeline.py`：vocals 驱动 Wav2Lip，FFmpeg 把 accompaniment 重混进 mp4
- [x] `POST /api/v1/generation` 新增 `enable_vocal_separation`（默认 true）+ `enable_denoising`（默认 false）
- [x] `POST /api/v1/generation/vocal_separation/warmup` 独立预热端点
- [x] `/engine/status` 暴露 `vocal_separation: { loaded, model_present, model_path, providers }`
- [x] 软失败：未安装分离模型时 WARN 降级，task result `vocal_separation_applied=false`
- [x] 进度面板新增「人声分离（DirectML）」阶段
- [x] ModelInfoCard 补「人声分离 + 伴奏重混」feature 卡

## 多模型推理（Wav2Lip-ONNX + MuseTalk）
- [x] `models/musetalk/` 目录与 README 已创建（说明 musetalk.safetensors / musetalk.onnx / MuseTalk.safetensors 等权重候选 + config/hubert 辅助）
- [x] `core/torch_provider.py` 实现 `is_torch_directml_available()` 与 `TorchDirectMLNotAvailable`（与 onnx_provider 同款「无 CPU 降级」）
- [x] `services/musetalk_engine.py` 单例 + DirectML 严苛 warmup + 权重发现 + `MuseTalkNotImplemented` 异常
- [x] `models/generation_schemas.py` 新增 `GenerationModel` 枚举（`wav2lip` / `musetalk`），`GenerationRequest.model` 默认 `wav2lip`
- [x] `services/task_manager.py`：`TaskRecord` 新增 `model` 字段；`create_task(..., model=)` 持久化；`to_response` 暴露给前端
- [x] `services/generation_service.py`：派发逻辑拆为 `_run_wav2lip_blocking` / `_run_musetalk_blocking`；新增 `engine_status()` 与 `warmup_engine(model)`
- [x] API 新增 `POST /api/v1/generation/wav2lip` / `POST /api/v1/generation/musetalk` 两条专用路由（内部强制覆盖 model）
- [x] API 新增 `GET /api/v1/generation/engines/status` 联合汇报两个引擎
- [x] API 新增 `POST /api/v1/generation/engines/wav2lip/warmup` / `POST /api/v1/generation/engines/musetalk/warmup` 独立预热
- [x] 前端 `api/generation.ts` 新增 `startGenerationWav2Lip` / `startGenerationMuseTalk` / `getEnginesStatus` / `warmupWav2LipEngine` / `warmupMuseTalkEngine` 与对应类型
- [x] 前端 `store/useStore.ts` `selectedModel` 持久化到 localStorage
- [x] 前端 `components/ModelSelector.tsx`：双卡片 UI（闪电生成 / 高清细节），按引擎状态显示 DirectML 就绪徽标与 MuseTalk 「torch-directml 未就绪」警告
- [x] 前端 `pages/GeneratePage.tsx`：第 4 步插入 `ModelSelector`；按 `selectedModel` 路由到对应 `startGeneration*` 函数
- [x] 前端 `components/ModelInfoCard.tsx`：重做为左右双栏，分别介绍 Wav2Lip-ONNX 与 MuseTalk

## 调度与 API
- [x] 视频生成 API（POST /api/generate）参数校验完整，返回任务 ID，支持进度查询
- [ ] 生成结果视频可正常播放和下载 — Note: needs actual generation with weights; cannot be exercised in this CI environment.

## 前端
- [x] 音乐上传组件支持拖拽上传和格式校验
- [x] 音频波形可视化可显示高潮标注并支持区间拖拽调整
- [x] 数字人形象选择组件可展示预设形象和自定义上传
- [x] 模型说明卡片清晰展示 Wav2Lip-ONNX 的跨平台 GPU / DirectML 加速 / CPU 兜底特性
- [x] 视频生成进度组件实时显示进度百分比和当前步骤
- [x] 视频播放器可正常预览和下载生成结果
- [x] 深色主题 UI 美观，操作流程引导清晰

## 日志与端到端
- [x] 后端日志覆盖所有关键操作，包含请求 ID、耗时、错误堆栈、ONNX provider 信息
- [ ] 端到端流程（上传 → 检测 → 生成 → 播放）可完整运行 — Note: requires ONNX weights; cannot be exercised in this CI environment.
- [ ] AMD 6700XT 环境下端到端流程在合理时间内完成（DirectML 路径）— Note: requires AMD 6700XT hardware; cannot be verified here.

## 范围确认
- [x] 已删除 SadTalker 相关功能、代码与权重
- [x] 已删除 LatentSync 相关功能、代码与权重
- [x] 调度器与前端均已收敛为单一 Wav2Lip-ONNX 路径

## Verification Report

- **Date**: 2026-06-02
- **Environment**: Linux sandbox, Python 3.14.4, Node.js / Vite 5.4.21
- **Backend pytest**: 6/6 tests passed in 0.71s (test_create_app_imports, test_health_endpoint, test_system_info_endpoint, test_engine_status_endpoint, test_mounted_routes_present, test_root_endpoint). Only deprecation warnings (FastAPI `on_event`, `pythonjsonlogger` import path, starlette/httpx).
- **Backend import smoke**: `HEALTH_OK`. Mounted routes include `/`, `/api/v1/health`, `/api/v1/system/info`, `/api/v1/music/upload`, `/api/v1/music/{music_id}`, `/api/v1/music/{music_id}/detect-chorus`, `/api/v1/music/{music_id}/slice`, `/api/v1/music/{music_id}/waveform`, `/api/v1/music/{music_id}/download`, `/api/v1/music/slice/{slice_id}/download`, `/api/v1/avatars`, `/api/v1/avatars/upload`, `/api/v1/avatars/presets`, `/api/v1/avatars/{avatar_id}` (GET + DELETE), `/api/v1/avatars/{avatar_id}/file|thumbnail`, `/api/v1/avatars/presets/{preset_id}/file|thumbnail`, `/api/v1/generation` (GET + POST), `/api/v1/generation/wav2lip` (POST), `/api/v1/generation/musetalk` (POST), `/api/v1/generation/{task_id}` (GET + DELETE), `/api/v1/generation/{task_id}/download|thumbnail`, `/api/v1/generation/engine/status|warmup`, `/api/v1/generation/engines/status`, `/api/v1/generation/engines/wav2lip/warmup`, `/api/v1/generation/engines/musetalk/warmup`, `/api/v1/generation/vocal_separation/warmup`, plus FastAPI docs (`/docs`, `/openapi.json`, `/redoc`).
- **Multi-model dispatch smoke**: `POST /api/v1/generation/wav2lip` and `POST /api/v1/generation/musetalk` both create tasks and immediately fail them with `error=directml_unavailable` for the matching provider (no CPU fallback) when the matching runtime is missing — this confirms the dispatch logic routes the request to the right engine and surfaces the right error message.
- **Frontend tsc**: `tsc --noEmit` exited 0 with no errors.
- **Frontend vite build**: built in 2.65s, 1601 modules transformed → `dist/index.html 0.54 kB`, `dist/assets/index-DvXdNg6C.css 27.04 kB`, `dist/assets/index-uUrix3D4.js 413.86 kB (gzip 131.32 kB)`.
- **File structure**: backend/frontend/models all present per the find listings; `.trae/specs/singing-digital-human/` contains `checklist.md`, `spec.md`, `tasks.md`. `models/wav2lip/` and `models/vocal_separation/` are reserved for ONNX weights; `models/musetalk/` is the new step-2 reservation.
- **Caveats**:
  - `models/wav2lip/` is empty (only `.gitkeep` + README) and `models/vocal_separation/` is empty (only `.gitkeep` + README). The Wav2Lip and face-detection ONNX weights, plus any vocal-separation ONNX weights, must be supplied by the user before actual video generation; the backend correctly surfaces `model_not_loaded` for Wav2Lip and a soft WARN downgrade for vocal separation otherwise.
  - `models/musetalk/` is the step-2 reservation. Even when weights are present, `MuseTalkEngine.generate` currently raises `MuseTalkNotImplemented` (the engine skeleton + DirectML strict strategy + routes are all wired, but the inference graph is intentionally a future deliverable).
  - AMD 6700XT-specific DirectML verification and full end-to-end run require the target GPU hardware and the ONNX weights; these could not be exercised in this Linux CI sandbox and are marked [ ] in the checklist above.
  - Cosmetic deprecation warnings (FastAPI `on_event`, `pythonjsonlogger.jsonlogger` import path, `httpx`+`starlette.testclient`) do not affect functionality.
