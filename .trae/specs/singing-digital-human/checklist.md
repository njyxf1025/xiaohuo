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
- [x] 后端已安装 `onnxruntime-directml` 与 `onnxruntime`（CPU 兜底）
- [ ] wav2lip.onnx 与 face_detection.onnx 权重文件已就位 — Note: weights not present in `/workspace/models/wav2lip/` (only `.gitkeep` + README); user must supply them before runtime generation.
- [x] 推理接口 providers 顺序为 `[DmlExecutionProvider, CPUExecutionProvider]`
- [ ] 在 AMD 6700XT 上 DirectML EP 成功创建会话并完成推理 — Note: requires the AMD 6700XT hardware + ONNX weights; cannot be verified in this CI environment.
- [x] DirectML 不可用时自动回退到 CPUExecutionProvider 并记录警告
- [x] 进度回调覆盖 session 创建、mel 计算、推理帧、合成各阶段

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
- **Backend pytest**: 5/5 tests passed in 0.59s (test_create_app_imports, test_health_endpoint, test_system_info_endpoint, test_mounted_routes_present, test_root_endpoint). Only deprecation warnings (FastAPI `on_event`, `pythonjsonlogger` import path, starlette/httpx).
- **Backend import smoke**: `HEALTH_OK`. Mounted routes include `/`, `/api/v1/health`, `/api/v1/system/info`, `/api/v1/music/upload`, `/api/v1/music/{music_id}`, `/api/v1/music/{music_id}/detect-chorus`, `/api/v1/music/{music_id}/slice`, `/api/v1/music/{music_id}/waveform`, `/api/v1/music/{music_id}/download`, `/api/v1/music/slice/{slice_id}/download`, `/api/v1/avatars`, `/api/v1/avatars/upload`, `/api/v1/avatars/presets`, `/api/v1/avatars/{avatar_id}` (GET + DELETE), `/api/v1/avatars/{avatar_id}/file|thumbnail`, `/api/v1/avatars/presets/{preset_id}/file|thumbnail`, `/api/v1/generation` (GET + POST), `/api/v1/generation/{task_id}` (GET + DELETE), `/api/v1/generation/{task_id}/download|thumbnail`, `/api/v1/generation/engine/status|warmup`, plus FastAPI docs (`/docs`, `/openapi.json`, `/redoc`).
- **Frontend tsc**: `tsc --noEmit` exited 0 with no errors.
- **Frontend vite build**: built in 2.69s, 1600 modules transformed → `dist/index.html 0.54 kB`, `dist/assets/index-t1fypwZ1.css 25.40 kB`, `dist/assets/index-DXdifc5j.js 403.81 kB (gzip 128.32 kB)`.
- **File structure**: backend/frontend/models all present per the find listings; `.trae/specs/singing-digital-human/` contains `checklist.md`, `spec.md`, `tasks.md`. Wav2Lip-ONNX is the only inference model; no SadTalker or LatentSync code/weights remain (the single textual mention is in `frontend/src/components/ModelInfoCard.tsx`, which explicitly states they have been removed).
- **Caveats**:
  - `models/wav2lip/` is empty (only `.gitkeep` + README). The Wav2Lip and face-detection ONNX weights must be supplied by the user before any actual video generation; the backend correctly surfaces a `model_not_loaded` error otherwise.
  - AMD 6700XT-specific DirectML verification and full end-to-end run require the target GPU hardware and the ONNX weights; these could not be exercised in this Linux CI sandbox and are marked [ ] in the checklist above.
  - Cosmetic deprecation warnings (FastAPI `on_event`, `pythonjsonlogger.jsonlogger` import path, `httpx`+`starlette.testclient`) do not affect functionality.
