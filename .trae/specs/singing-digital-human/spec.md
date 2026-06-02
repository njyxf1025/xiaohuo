# 会唱歌的数字人 Spec

## Why
用户拥有本地音乐但无法让数字人演唱出来。需要一个端到端 Web 应用：上传音乐后自动检测高潮部分，截取片段由数字人音画同步、口型一致地演唱出来，呈现美观的交互界面。模型层只保留 Wav2Lip-ONNX（ONNX Runtime + DirectML），通过 DirectML 跨平台覆盖 AMD/NVIDIA/Intel GPU，**禁止 CPU 降级**。为彻底解决「带伴奏歌曲口型抖动」问题，引入 **ONNX 人声分离** 子模块（与 Wav2Lip 共用同一 DirectML EP，CPU 兜底同样禁用），推理时纯人声驱动唇形，最终视频用 FFmpeg 把伴奏重混回音轨。

**高潮检测采用「pychorus 自动检测 + Wavesurfer.js 可视化与微调」的混合方案**——理由见末尾「方案对比：pychorus vs Wavesurfer.js」一节，结论是两者并非互斥的替代关系，而是互补的协作关系。

## What Changes
- 构建全栈 Web 应用：Python 后端（FastAPI）+ 现代前端（React + Vite + TailwindCSS）
- 集成 Wav2Lip-ONNX 唇形同步模型（唯一模型）：使用 ONNX Runtime + DirectML 在 AMD/NVIDIA/Intel GPU 上推理，**CPU 兜底已禁用**
- 集成 ONNX 人声分离子模块（Spleeter / UVR5 / Mel-Band-Roformer / htdemucs 等 ONNX 导出，与 Wav2Lip 共用同一 DirectML EP）：推理前先把纯人声送进 Wav2Lip，最终视频用 FFmpeg 把伴奏重混回音轨
- 音乐上传与高潮自动检测（pychorus + librosa），前端波形可视化与区间拖拽
- GPU 抽象层，支持 AMD（DirectML/ROCm）、NVIDIA（DirectML/CUDA）、Intel（DirectML）；无 DirectML 时**直接报错**，禁止 CPU 回退
- 数字人形象管理：自定义上传（图片/视频，含人脸检测）+ 预设形象
- 详细结构化后端日志：请求 ID、阶段耗时、错误堆栈、GPU/Provider 信息
- 美观深色主题前端，含音频波形、视频预览、生成进度动画（新增「人声分离（DirectML）」阶段）
- **BREAKING（针对原三模型方案）**：删除 SadTalker、LatentSync 两种模型及其相关代码/权重/任务；模型调度器简化为 Wav2Lip-ONNX 单一路径
- **BREAKING（针对原 ONNX 部署）**：所有 ONNX 推理统一走 DirectML，移除全部 CPUExecutionProvider 路径

## Impact
- Affected specs: 新项目，无已有 spec
- Affected code: 全新项目（backend/、frontend/、models/、data/）
- 关键依赖新增：`onnxruntime-directml`、`onnxruntime`（CPU 兜底）、Wav2Lip 导出的 `.onnx` 权重文件
- 关键依赖移除：原 SadTalker、LatentSync 的预训练权重与 PyTorch 推理分支
- 后端不再需要 torch（仅在 Wav2Lip 必要的 mel 谱/图像预处理使用 numpy+cv2 即可），减小安装体积

## ADDED Requirements

### Requirement: 音乐上传与高潮检测
系统 SHALL 提供音乐文件上传功能，支持 MP3/WAV/M4A/FLAC 格式，上传后自动检测歌曲高潮段落，用户可预览高潮片段并手动调整起止时间。

#### Scenario: 上传音乐并自动检测高潮
- **WHEN** 用户上传一个音乐文件
- **THEN** 系统解析音频，使用 pychorus 库检测高潮段落，返回高潮起止时间，并在前端波形图上高亮标注

#### Scenario: 手动调整高潮区间
- **WHEN** 用户对自动检测的高潮区间不满意
- **THEN** 用户可在波形图上拖拽调整起止时间，或手动输入时间，系统实时预览截取片段

### Requirement: 数字人形象管理
系统 SHALL 支持用户上传参考图片（单张人脸正面照）或参考视频作为数字人形象源，并提供预设形象供选择。

#### Scenario: 上传自定义形象
- **WHEN** 用户上传一张正面人脸照片或一段包含人脸的短视频
- **THEN** 系统验证图片/视频中是否包含可识别人脸，验证通过后保存为可用形象

#### Scenario: 选择预设形象
- **WHEN** 用户从预设形象列表中选择一个
- **THEN** 系统加载该预设形象的预览图和必要数据

### Requirement: 唇形同步视频生成（Wav2Lip-ONNX）
系统 SHALL 使用 Wav2Lip 的 ONNX 导出模型，通过 ONNX Runtime + DirectML 在多平台 GPU 上推理，将截取的高潮音频与数字人形象合成口型同步的演唱视频。**CPU 兜底禁用**：DirectML 不可用时系统直接返回 HTTP 503，绝不静默回退到 CPUExecutionProvider。

#### Scenario: 使用 Wav2Lip-ONNX 生成视频
- **WHEN** 用户点击生成按钮
- **THEN** 系统使用 ONNX Runtime 加载 wav2lip.onnx 权重，DirectML provider 优先（CPU 兜底），将高潮音频与数字人形象合成唇形同步视频；记录推理设备、provider、耗时与输出分辨率

#### Scenario: 生成进度反馈
- **WHEN** 视频正在生成中
- **THEN** 前端实时显示生成进度百分比和当前步骤（如"正在加载 ONNX 推理会话"、"正在提取音频特征"、"正在生成唇形"、"正在合成视频"）

### Requirement: GPU 多平台支持（DirectML 唯一）
系统 SHALL 通过 GPU 抽象层支持 AMD（DirectML/ROCm）、NVIDIA（DirectML/CUDA）、Intel（DirectML）显卡，Wav2Lip 推理**仅使用 DirectML provider**。CPU 降级**已禁用**：若 DirectML 不可用（驱动缺失/包未装/无 DML 设备），系统必须立即返回 HTTP 503 并在日志中以 FATAL 级别报告，绝不静默降级到 CPU 推理。

#### Scenario: AMD GPU 环境（DirectML）
- **WHEN** 系统检测到 AMD GPU 且已安装 onnxruntime-directml
- **THEN** Wav2Lip 推理使用 DirectML EP；日志记录 GPU 型号、DirectML 设备 ID、显存使用

#### Scenario: NVIDIA GPU 环境（DirectML）
- **WHEN** 系统检测到 NVIDIA GPU 且已安装 onnxruntime-directml
- **THEN** Wav2Lip 推理使用 DirectML EP；日志记录 GPU 型号、DirectML 设备 ID、显存使用

#### Scenario: Intel 核显/Intel Arc 环境
- **WHEN** 系统检测到 Intel GPU
- **THEN** Wav2Lip 推理使用 DirectML EP；日志记录 Intel 设备信息

#### Scenario: DirectML 不可用（驱动/包/设备任一缺失）
- **WHEN** `onnxruntime-directml` 未安装、或 onnxruntime 不可用、或没有任何 DML 设备
- **THEN** 系统立刻报错：`/api/v1/health` 返回 503 `status=unavailable`；`/api/v1/system/info` 返回 503；`/api/v1/generation` 返回 503 `error=directml_unavailable`；`/api/v1/generation/{id}` 任务进入 `failed` 状态 `error="DirectML unavailable: ..."`；启动日志以 **FATAL** 级别说明缺失原因
- **THEN** **绝不**降级到 CPUExecutionProvider（CPU 太慢，推理实际不可用）

### Requirement: 音频降噪与人声分离
系统 SHALL 在 Wav2Lip 推理前，先对截取的高潮音频做 **ONNX 人声分离**，把纯人声送进 Wav2Lip 驱动唇形；最终视频用 FFmpeg 把分离出的伴奏重混回音轨，从而：
- 避免重低音伴奏导致的口型抖动
- 维持用户听到的完整歌曲体验

#### Scenario: 启用人声分离（默认）
- **WHEN** 用户提交生成请求且 `enable_vocal_separation=true`（默认）
- **THEN** 系统调用 ONNX 分离模型（U5R / Spleeter / Mel-Band-Roformer / htdemucs 等任一 ONNX 导出）从 DirectML EP 推理，返回 `vocals.wav` 与 `accompaniment.wav`；Wav2Lip 用 vocals 跑唇形，FFmpeg 用 accompaniment 合成最终 mp4
- **THEN** 进度面板出现「人声分离（DirectML）」阶段，task result 中 `vocal_separation_applied=true`，并返回 `vocals_path` / `accompaniment_path`

#### Scenario: 分离模型未安装
- **WHEN** `enable_vocal_separation=true` 但 `models/vocal_separation/` 下没有任何 ONNX 权重
- **THEN** 系统**不报错**，降级为用原始音频驱动 Wav2Lip（用户口型可能轻微抖动，但流程仍跑得通）；日志 WARN 级别说明降级原因
- **THEN** task result 中 `vocal_separation_applied=false`，`vocals_path=null`，`accompaniment_path=null`

#### Scenario: DirectML 不可用且启用了人声分离
- **WHEN** `enable_vocal_separation=true` 但 DirectML 不可用
- **THEN** 系统立刻返回 503 `error=directml_unavailable`，任务进入 failed 状态（**不会**降级到 CPU 跑分离模型，因为 CPU 推理不可用）

#### Scenario: 关闭人声分离
- **WHEN** 用户在生成页关掉「启用人声分离」开关
- **THEN** 系统跳过 vocal_separation 阶段，直接用原始音频驱动 Wav2Lip；最终视频音频 = 原始音乐；task result 中 `vocal_separation_applied=false`

### Requirement: 详细后端日志
系统 SHALL 在所有关键操作中记录详细日志，包括请求参数、处理步骤、耗时、错误堆栈等，确保任何问题都能被追踪和定位。

#### Scenario: 视频生成日志
- **WHEN** 用户发起视频生成请求
- **THEN** 系统记录：请求 ID、用户参数（音频时长、形象 ID）、ONNX 会话创建、provider 选择、每个处理步骤的开始/结束时间、显存/内存使用、最终结果状态

#### Scenario: 错误追踪日志
- **WHEN** 任何处理步骤发生错误
- **THEN** 系统记录完整的错误堆栈、输入参数快照、当前处理阶段、ONNX provider 信息，并返回用户友好的错误提示

### Requirement: 美观的前端界面
系统 SHALL 提供现代化、美观的 Web 界面，包含音频波形可视化、视频预览播放器、生成进度动画等。

#### Scenario: 首页体验
- **WHEN** 用户打开应用首页
- **THEN** 看到清晰的操作流程引导（上传音乐 → 选择高潮 → 选择形象 → 生成视频），界面采用深色主题，视觉层次分明

#### Scenario: 音频波形交互
- **WHEN** 音乐上传完成
- **THEN** 显示音频波形图，高潮区间高亮标注，用户可拖拽调整区间，播放预览截取片段

## MODIFIED Requirements
无（新项目）。

## REMOVED Requirements
- SadTalker 模型及其全部 3DMM / 头部姿态 / 表情控制相关功能（原 Task 6）
- LatentSync 模型及其扩散模型推理路径（原 Task 7）
- 原多模型调度器（Task 8.1）改为 Wav2Lip-ONNX 单一调度路径
- 前端三模型对比卡片（Task 9.5）改为单一模型说明 + ONNX 推理特性介绍

## 方案对比：pychorus vs Wavesurfer.js

> 结论先行：**两者不是互斥的替代关系，而是互补的协作关系**。pychorus 解决「自动找到高潮在哪里」，Wavesurfer.js 解决「把结果画出来让用户微调」。本项目采用「pychorus 后端检测 + Wavesurfer.js 前端可视化与微调」的混合方案。

### 方案 A：pychorus（后端自动检测）

**原理**：pychorus 是基于 chroma 频谱重复度检测的 Python 库。它先把音频切成短片段，提取每段的 chroma 特征（12 维色度向量），再用一个滑动窗口与自相似矩阵寻找「重复出现次数最多、能量最集中」的段落作为候选高潮。

**优点**
- 自动化程度高：上传即得推荐区间，零用户操作
- 算法成熟：对流行/电子/摇滚等重复结构明显的歌曲效果较好
- 服务端可调优：可针对曲库批量调参、离线评测准确率
- 内置兜底：本项目 `services/chorus.py` 在 pychorus 失败时回退到 librosa loudest window（能量最大的 20 秒窗口），保证永远有结果
- 离线友好：上传后用户可以断开浏览器，等结果回来再确认

**缺点**
- Python 依赖：pychorus 在 PyPI 上维护不活跃，pip 安装常失败 → 必须有 librosa 兜底（本项目已实现）
- 算法固定：对人声/纯音乐/复杂编曲识别准确度下降
- 不提供可视化：用户看不到「为什么这是高潮」
- 一次只能给一个推荐值：用户无法表达「我想要副歌第二遍」

### 方案 B：Wavesurfer.js（前端可视化 + 手动框选）

**原理**：Wavesurfer.js 本身是**音频波形渲染与播放库，不做自动检测**。但配合其 Regions 插件可让用户在画布上**手动拖拽两个手柄**框选起止时间，本质是「人肉检测」。

**优点**
- 可视化效果最佳：实时波形、缩放、播放头联动，所见即所得
- 交互极强：拖拽即听，配合播放头确认方便
- 离线可用：音频载入后无需服务端交互
- 不依赖任何后端算法
- 灵活度最高：用户可以选副歌、副歌第二遍、bridge、任何位置

**缺点**
- **不会自动检测**：用户必须自己听、自己判断，对不熟悉歌曲的人不友好
- 用户体验负担：每首歌都要点十几下才能选出 20 秒
- 没有算法保障：选错区间得不到任何提示
- 增加前端包体积：Wavesurfer.js + regions 插件约 ~80KB
- 单纯用它无法完成「让数字人自动唱副歌」这一核心诉求

### 维度对比矩阵

| 维度 | pychorus（后端） | Wavesurfer.js（前端） | 混合（本项目） |
| --- | --- | --- | --- |
| 自动检测 | ✅ 是 | ❌ 否 | ✅ 是 |
| 可视化呈现 | ❌ 否 | ✅ 强 | ✅ 强 |
| 用户微调 | ❌ 不支持 | ✅ 原生 | ✅ 原生 |
| 离线工作 | ❌ 需服务端 | ✅ 是 | ⚠️ 检测需服务端 |
| 上手成本 | 🟢 零 | 🔴 高 | 🟢 低 |
| 准确度天花板 | 🟡 受限于算法 | 🟢 仅受限于用户 | 🟢 兼具 |
| 失败兜底 | 🟡 需自行实现 | 🟢 永远可用 | 🟢 双重兜底 |
| 实施复杂度 | 🟢 中（一个 Python 函数） | 🟢 中（一个 React 组件） | 🟡 略高（要联调两边） |
| 适合谁 | 大量批处理 | 音乐人/精细创作 | 通用 C 端用户 |

### 业界参考
- **Spotify / 网易云音乐「分享歌曲片段」**：自动识别 + 可拖拽微调（与本方案一致）
- **LALAL.AI / Moises.ai**：自动检测 + 波形可视化（与本方案一致）
- **Audacity / 传统音频编辑器**：纯手动框选（对应方案 B）
- **Shazam / ACRCloud**：纯算法识别（对应方案 A）

### 为什么混合方案最优

1. **自动化 + 灵活性兼得**：80% 用户用默认值即可满意；20% 的挑剔用户可拖拽微调
2. **用户感知路径最短**：上传 → 看到推荐区间 → 试听 → 接受/微调，3 步完成
3. **鲁棒性最强**：pychorus 失败 → librosa 兜底 → 仍有结果；前端微调 → 永不卡死
4. **复用现有资产**：pychorus 已在 `services/chorus.py`，Wavesurfer.js 已在 `components/WaveformPlayer.tsx`，**本次实现天然就是混合方案**，无需额外开发
5. **数据可积累**：后端可记录「用户是否调整了自动检测结果」作为后续算法迭代的反馈信号

### 当前实现对照

- **后端**：[backend/services/chorus.py](file:///workspace/backend/services/chorus.py) — pychorus 优先，长度候选 [20, 15, 25, 30, 10] 秒，librosa loudest window 兜底
- **API**：`POST /api/v1/music/{music_id}/detect-chorus` + 上传后异步调度，返回 `chorus: { start_sec, end_sec, confidence }`
- **前端**：[frontend/src/components/WaveformPlayer.tsx](file:///workspace/frontend/src/components/WaveformPlayer.tsx) — Wavesurfer.js 7 渲染 peaks、两个 pointer-event 手柄拖拽调整、`onChange({start,end})` 回调
- **协作流**：上传 → 后端自动检测 → 前端把推荐区间画在波形上 → 用户拖拽微调 → 点击确认触发截取 API

## 多模型推理架构（Wav2Lip-ONNX + MuseTalk）

> 在保留 Wav2Lip-ONNX 作为默认 / 闪电生成路径的基础上，**新增 MuseTalk 作为高画质可选路径**，统一在 FastAPI 后面暴露两条独立路由，前端用一个统一的 `ModelSelector` 组件做单点切换。两条路径共用同一份 DirectML 严格策略（**无 CPU 降级**），由前端与后端各自的 `GenerationModel` 枚举同步。

### 架构图

```
                    ┌─── [前端统一控制台] (React + Vite + Tailwind) ───┐
                    │                                                  │
         (用户选 Wav2Lip 闪电生成)                            (用户选 MuseTalk 高清细节)
                    │                                                  │
                    ▼                                                  ▼
      POST /api/v1/generation/wav2lip             POST /api/v1/generation/musetalk
                    │                                                  │
          ┌─────────┴─────────┐                              ┌─────────┴─────────┐
          │ Wav2Lip-ONNX 引擎  │                              │   MuseTalk 引擎    │
          │ (ONNXRuntime-DML)  │                              │ (PyTorch-DirectML) │
          └─────────┬─────────┘                              └─────────┬─────────┘
                    │                                                  │
                    └───────────► [ 共享硬件：AMD 6700XT ] ◄──────────┘
```

> 兼容路由 `POST /api/v1/generation` 仍可接收 `model: "wav2lip" | "musetalk"`，效果与两条专用路由一致。

### 落地三步走（明确写在 spec 里，避免一上来同时搞两个）

1. **第一步（已落地 · Wav2Lip 核心流程）**
   - 拉取 wav2lip-onnx 源码 + FastAPI 封装
   - 前端 4 步引导：上传 → 选高潮 → 选形象 → 生成
   - 验证 AMD 6700XT 驱动 + onnxruntime-directml 整条管线
2. **第二步（已部分落地 · MuseTalk 骨架 + 路由）**
   - 后端实现 [services/musetalk_engine.py](file:///workspace/backend/services/musetalk_engine.py) 单例 + DirectML 严苛策略 + 权重发现
   - 新增 `POST /api/v1/generation/musetalk` 路由，**目前返回 `code="not_implemented"` 状态**，等待推理图实现
   - 前端 `ModelSelector` 仍允许选 MuseTalk，但会在卡片上展示「Step-2 路线」徽标与 torch-directml 状态
3. **第三步（未来 · 完整整合）**
   - 把 MuseTalk 真实推理图接入 `MuseTalkEngine.generate`
   - 移除 `MuseTalkNotImplemented` 抛出；前端卡片升级为「可点击 + 实测对比」
   - 进一步加语音克隆、背景替换等 Linly-Talker 风格能力

### Requirement: 多模型推理调度（Dispatch by model）

系统 SHALL 在同一个 `GenerationService` 内根据请求的 `model` 字段把任务派发到对应的引擎，并对外暴露两条专用路由 + 一条兼容路由。

#### Scenario: 默认走 Wav2Lip
- **WHEN** 前端未指定 `model` 或传 `model="wav2lip"`
- **THEN** `GenerationService` 派发到 `Wav2LipEngine`；调用链路为 `core/onnx_provider` → `services/wav2lip_engine` → `services/wav2lip_pipeline`；结果里 `model="wav2lip"`

#### Scenario: 显式选择 MuseTalk
- **WHEN** 前端调用 `POST /api/v1/generation/musetalk` 或 `POST /api/v1/generation` 且 `model="musetalk"`
- **THEN** `GenerationService` 派发到 `MuseTalkEngine`；当前实现做 `warmup` + DirectML 严苛校验，然后因 `MuseTalkNotImplemented` 失败；task 进入 `failed` 状态 `error="musetalk not implemented: step-2 deliverable. Wav2Lip-ONNX is the active engine."`

#### Scenario: 专用路由与兼容路由
- **WHEN** 任意引擎被选择
- **THEN** `POST /api/v1/generation/wav2lip` 与 `POST /api/v1/generation/musetalk` 内部会强制覆盖 `payload.model` 后再走统一派发；`POST /api/v1/generation` 仅信任客户端传上来的 `model`，无值时回退到 `wav2lip`

### Requirement: 引擎状态端点（同时汇报两个引擎）

系统 SHALL 提供 `GET /api/v1/generation/engines/status` 端点，同时返回 `wav2lip` 与 `musetalk` 的 DirectML 就绪状态、provider 标签、加载状态、最近一次错误、权重路径；并提供 `POST /api/v1/generation/engines/wav2lip/warmup` 与 `POST /api/v1/generation/engines/musetalk/warmup` 两条独立预热端点。

#### Scenario: 至少一个引擎可用
- **WHEN** `wav2lip.directml_ready=true` 或 `musetalk.directml_ready=true`
- **THEN** `GET /api/v1/generation/engines/status` 返回 200 + `engines.{wav2lip,musetalk}` 完整结构

#### Scenario: 两个引擎都不可用
- **WHEN** 两条路径的 DirectML probe 都失败
- **THEN** 端点返回 503，但 payload 仍包含两个引擎的失败原因，方便用户排查

### Requirement: 引擎严苛策略（MuseTalk 同样不降级 CPU）

MuseTalk 引擎 SHALL 沿用 Wav2Lip 引擎的「DirectML 唯一 + 拒绝 CPU 降级」策略。原因：PyTorch 在 CPU 上跑扩散 UNet 慢到无法使用，与 Wav2Lip 的 CPU 不可用情况同源。

#### Scenario: torch-directml 不可用
- **WHEN** `torch-directml` 未安装或 `torch_directml.device_count() == 0`
- **THEN** `MuseTalkEngine.warmup()` 在 `is_torch_directml_available()` 阶段立刻返回 False，`last_error` 含 `directml_unavailable: ...`；提交任务到 `/generation/musetalk` 会被 `_probe_directml_for_model("musetalk")` 在派发前直接 fail_task，错误码 `directml_unavailable`

### Requirement: 前端模型选择 UI

系统 SHALL 提供 `ModelSelector` 组件，在 GeneratePage 第 4 步以两张并排卡片（闪电 / 高清）让用户做单选；选择结果通过 Zustand `selectedModel` 持久化到 localStorage，刷新页面后仍保留。

#### Scenario: 切换推理模型
- **WHEN** 用户点击 MuseTalk 卡片
- **THEN** `useStore.setSelectedModel("musetalk")` 触发；`ModelInfoCard` 高亮更新；`useStore.reset()` 时回到 `wav2lip`

#### Scenario: MuseTalk 端 DirectML 缺失提示
- **WHEN** `/api/v1/generation/engines/status` 返回 `engines.musetalk.directml_ready=false`
- **THEN** MuseTalk 卡片在 `ModelSelector` 内显示「torch-directml 未就绪」警告，但用户仍可点击（提交后会被后端 503 拒绝，方便演示整套严格策略）
