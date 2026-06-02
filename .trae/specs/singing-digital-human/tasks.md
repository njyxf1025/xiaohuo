# Tasks

- [x] Task 1: 项目初始化与基础架构搭建
  - [x] SubTask 1.1: 创建项目目录结构（backend/、frontend/、models/、data/）
  - [x] SubTask 1.2: 初始化 Python 后端项目（FastAPI + pyproject.toml + 依赖管理）
  - [x] SubTask 1.3: 初始化前端项目（React + Vite + TailwindCSS）
  - [x] SubTask 1.4: 配置后端日志系统（结构化日志，请求 ID 追踪）
  - [x] SubTask 1.5: 配置 CORS 和前后端联调环境

- [x] Task 2: GPU 抽象层与设备检测
  - [x] SubTask 2.1: 实现 GPU 检测模块（自动识别 AMD/NVIDIA/Intel/CPU）
  - [x] SubTask 2.2: 实现 GPU 抽象接口（统一 device 管理、内存监控、ONNX provider 选择）
  - [x] SubTask 2.3: 编写 GPU 检测和 provider 切换的日志记录

- [x] Task 3: 音乐上传与高潮检测
  - [x] SubTask 3.1: 实现音乐文件上传 API（支持 MP3/WAV/M4A/FLAC）
  - [x] SubTask 3.2: 集成 pychorus 实现高潮自动检测
  - [x] SubTask 3.3: 实现音频截取 API（根据起止时间截取片段）
  - [x] SubTask 3.4: 实现音频波形数据生成 API（供前端可视化）

- [x] Task 4: 数字人形象管理
  - [x] SubTask 4.1: 实现形象上传 API（图片/视频，含人脸检测验证）
  - [x] SubTask 4.2: 实现预设形象管理（内置 2-3 个默认形象）
  - [x] SubTask 4.3: 实现形象列表查询和预览 API

- [x] Task 5: 唇形同步模型集成 - Wav2Lip-ONNX（唯一模型）
  - [x] SubTask 5.1: 安装推理依赖 `pip install onnxruntime-directml`（不再需要 `onnxruntime` CPU 兜底）
  - [x] SubTask 5.2: 获取/导出 wav2lip_hq.onnx / wav2lip.onnx 与 face_detection.onnx / s3fd.onnx 权重
  - [x] SubTask 5.3: 封装 Wav2Lip-ONNX 推理接口（输入：音频 + 形象，输出：视频；providers 严格限定：`["DmlExecutionProvider"]`，拒绝 CPU 兜底）
  - [x] SubTask 5.4: 强制使用 SessionOptions.execution_mode = ORT_SEQUENTIAL（DirectML 不支持并行图执行）
  - [x] SubTask 5.5: 实现多平台 GPU provider 自适应（AMD/NVIDIA/Intel 走 DirectML，无 DML 立即抛 DirectMLNotAvailable 503）
  - [x] SubTask 5.6: 实现视频生成进度回调机制（session 创建、mel 计算、推理帧、合成）

- [x] Task 5b: ONNX 人声分离子模块（DirectML 强约束）
  - [x] SubTask 5b.1: 创建 `models/vocal_separation/` 目录与 README（说明支持的 ONNX 模型候选：vocal_separation.onnx / mel_band_roformer.onnx / htdemucs.onnx / spleeter_2stems.onnx / mdx_q.onnx / kim_vocal.onnx）
  - [x] SubTask 5b.2: 实现 `services/vocal_separation.py`：单例 VocalSeparator，ONNX Runtime + DirectML（CPU 兜底禁用，顺序执行模式）
  - [x] SubTask 5b.3: 实现 `separate(audio_path, output_dir)` → (vocals.wav, accompaniment.wav)；输出 1-stem 模型时合成静音伴奏
  - [x] SubTask 5b.4: 集成到 `services/wav2lip_pipeline.py`：截取后先做分离，纯人声驱动 Wav2Lip，FFmpeg 把伴奏重混到最终 mp4
  - [x] SubTask 5b.5: API 扩展：`POST /api/v1/generation` 新增 `enable_vocal_separation`（默认 true）与 `enable_denoising`（默认 false，预留 resemble-denoiser）
  - [x] SubTask 5b.6: 新增 `POST /api/v1/generation/vocal_separation/warmup`；`/engine/status` 暴露 `vocal_separation` 子对象
  - [x] SubTask 5b.7: 进度面板新增「人声分离（DirectML）」阶段；ModelInfoCard 补「人声分离 + 伴奏重混」feature
  - [x] SubTask 5b.8: 软失败：分离模型未安装时 WARN 降级到原始音频（不阻塞任务）

- [x] Task 5c: 多模型推理调度（Wav2Lip-ONNX + MuseTalk，step-1/step-2 分阶段交付）
  - [x] SubTask 5c.1: 创建 `models/musetalk/` 目录与 README（说明支持的权重候选：musetalk.safetensors / musetalk.onnx / musetalk.pt / MuseTalk.safetensors / musetalk_fp16.safetensors / musetalk_fp32.safetensors + config.yaml / hubert.pt 等辅助权重）
  - [x] SubTask 5c.2: 实现 `core/torch_provider.py`：torch / torch-directml 探测，`TorchDirectMLNotAvailable` 异常，**与 Wav2Lip 同款的「无 CPU 降级」严苛策略**
  - [x] SubTask 5c.3: 实现 `services/musetalk_engine.py`：`MuseTalkEngine` 单例，warmup 阶段做 DirectML 严苛校验，权重发现，定义 `MuseTalkNotImplemented`（step-2 真实推理图的占位异常）
  - [x] SubTask 5c.4: 更新 `models/generation_schemas.py`：新增 `GenerationModel` 枚举（`wav2lip` / `musetalk`），`GenerationRequest.model` 默认 `wav2lip`
  - [x] SubTask 5c.5: `services/task_manager.py`：`TaskRecord` 新增 `model` 字段（默认 `wav2lip`），`create_task(..., model=)` 持久化，`to_response` 暴露给前端
  - [x] SubTask 5c.6: `services/generation_service.py`：派发逻辑拆分为 `_run_wav2lip_blocking` / `_run_musetalk_blocking`；新增 `engine_status()` 与 `warmup_engine(model)` 助手
  - [x] SubTask 5c.7: `api/generation.py`：新增 `POST /api/v1/generation/wav2lip` 与 `POST /api/v1/generation/musetalk` 两条专用路由（内部强制覆盖 `payload.model`）；新增 `GET /api/v1/generation/engines/status`、`POST /api/v1/generation/engines/wav2lip/warmup`、`POST /api/v1/generation/engines/musetalk/warmup`
  - [x] SubTask 5c.8: 前端 `api/generation.ts`：新增 `startGenerationWav2Lip` / `startGenerationMuseTalk` / `getEnginesStatus` / `warmupWav2LipEngine` / `warmupMuseTalkEngine`，以及 `GenerationModel` / `EngineSlot` / `EnginesStatusResponse` 类型
  - [x] SubTask 5c.9: 前端 `store/useStore.ts`：`selectedModel` 持久化到 localStorage（与 `selectedAvatar` 同款）
  - [x] SubTask 5c.10: 前端 `components/ModelSelector.tsx`：双卡片 UI（闪电生成 / 高清细节），读 `engines.status` 显示每条路径 DirectML 就绪状态，MuseTalk 缺失 torch-directml 时显示「torch-directml 未就绪」警告
  - [x] SubTask 5c.11: 前端 `pages/GeneratePage.tsx`：在第 4 步插入 `ModelSelector`；提交时按 `selectedModel` 路由到 `startGenerationWav2Lip` / `startGenerationMuseTalk`
  - [x] SubTask 5c.12: 前端 `components/ModelInfoCard.tsx`：重做为左右双栏，分别介绍 Wav2Lip-ONNX 与 MuseTalk，强调共用 DirectML 严苛策略
  - [x] SubTask 5c.13: 文档：`spec.md` 增加「多模型推理架构」段落，`tasks.md` 记录本任务，`checklist.md` 增加对应验证项

- [x] Task 6: 视频生成 API 与结果管理
  - [x] SubTask 6.1: 实现视频生成 API（POST /api/generate，含参数校验）
  - [x] SubTask 6.2: 实现生成任务状态查询 API（进度、结果、错误信息）
  - [x] SubTask 6.3: 实现生成结果视频的存储和下载 API

- [x] Task 7: 前端界面开发
  - [x] SubTask 7.1: 搭建页面布局和路由（首页、生成页、历史记录页）
  - [x] SubTask 7.2: 实现音乐上传组件（拖拽上传、格式校验）
  - [x] SubTask 7.3: 实现音频波形可视化组件（WaveSurfer.js 集成、高潮标注、区间拖拽）
  - [x] SubTask 7.4: 实现数字人形象选择组件（预设卡片 + 自定义上传）
  - [x] SubTask 7.5: 实现模型说明卡片（Wav2Lip-ONNX 特性：跨平台 GPU、DirectML 加速、CPU 兜底）
  - [x] SubTask 7.6: 实现视频生成进度组件（进度条 + 步骤提示）
  - [x] SubTask 7.7: 实现视频播放器组件（预览 + 下载）
  - [x] SubTask 7.8: 实现深色主题和整体 UI 美化

- [x] Task 8: 端到端集成测试与优化
  - [x] SubTask 8.1: 编写完整流程集成测试（上传 → 检测 → 生成 → 播放）
  - [x] SubTask 8.2: 验证 AMD 6700XT 环境下的 ONNX + DirectML 推理
  - [x] SubTask 8.3: 性能优化（ONNX 会话缓存、推理批处理）
  - [x] SubTask 8.4: 日志完整性验证（确保所有错误可追踪）

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 1]
- [Task 4] depends on [Task 1]
- [Task 5] depends on [Task 2]（Wav2Lip-ONNX 需要 GPU 抽象层决定 provider 优先级）
- [Task 5b] depends on [Task 2, Task 5]（人声分离与 Wav2Lip 共享 DirectML EP / 同一引擎基类）
- [Task 6] depends on [Task 5, Task 5b]
- [Task 7] depends on [Task 1]
- [Task 8] depends on [Task 6, Task 7]
- Task 3, Task 4, Task 5 可并行开发
- Task 5b 可在 Task 5 完成后并行开发
- Task 7 的各子任务在前端框架搭建后可并行开发
