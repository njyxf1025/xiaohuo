# 会唱歌的数字人 Spec

## Why
用户拥有本地音乐但无法让数字人演唱出来。需要一个端到端Web应用：上传音乐后自动检测高潮部分，截取片段由数字人音画同步、口型一致地演唱出来，呈现美观的交互界面。同时通过 Wav2Lip-ONNX + DirectML 推理后端替代原生 PyTorch Wav2Lip，在 AMD/NVIDIA/Intel 多平台 GPU 上获得更轻量、更可移植的部署体验。

## What Changes
- 构建全栈 Web 应用：Python 后端（FastAPI）+ 现代前端（React + Vite + TailwindCSS）
- 集成三种唇形同步模型，用户可自由切换：
  - **Wav2Lip-ONNX（默认，推荐）**：使用 ONNX Runtime + DirectML 后端推理，跨平台 GPU 加速
  - **SadTalker**：3DMM 驱动，支持头部姿态与表情控制
  - **LatentSync**：扩散模型，质量最高
- 音乐上传与高潮自动检测（pychorus + librosa），前端波形可视化与区间拖拽
- GPU 抽象层，支持 AMD（DirectML/ROCm）、NVIDIA（DirectML/CUDA）、Intel（DirectML）、CPU 降级
- 数字人形象管理：自定义上传（图片/视频，含人脸检测）+ 预设形象
- 详细结构化后端日志：请求 ID、阶段耗时、错误堆栈、GPU 内存
- 美观深色主题前端，含音频波形、视频预览、模型对比卡片、生成进度动画
- **BREAKING（针对原 Wav2Lip 子任务）**：Wav2Lip 推理从 PyTorch + CUDA/ROCm 迁移至 ONNX Runtime + DirectML（CPU 兜底），需 `pip install onnxruntime-directml`

## Impact
- Affected specs: 新项目，无已有 spec
- Affected code: 全新项目（backend/、frontend/、models/、data/）
- 关键依赖新增：`onnxruntime-directml`、`onnxruntime`（CPU 兜底）、Wav2Lip 导出的 `.onnx` 权重文件
- 关键依赖移除：原 Wav2Lip 推理所需的 PyTorch 推理分支（非 SadTalker/LatentSync 共用部分）

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

### Requirement: 唇形同步视频生成（Wav2Lip-ONNX 默认）
系统 SHALL 默认使用 Wav2Lip 的 ONNX 导出模型，通过 ONNX Runtime + DirectML 在多平台 GPU 上推理；保留 SadTalker 与 LatentSync 作为可选高质量模型。

#### Scenario: 使用 Wav2Lip-ONNX 生成视频
- **WHEN** 用户选择 Wav2Lip 模型并点击生成
- **THEN** 系统使用 ONNX Runtime 加载 wav2lip.onnx 权重，DirectML provider 优先（CPU 兜底），将高潮音频与数字人形象合成唇形同步视频；记录推理设备、provider、耗时与输出分辨率

#### Scenario: 使用 SadTalker 生成视频
- **WHEN** 用户选择 SadTalker 模型并点击生成
- **THEN** 系统使用 SadTalker 模型生成 3DMM 驱动的说话人脸动画视频，支持头部姿态和表情控制

#### Scenario: 使用 LatentSync 生成视频
- **WHEN** 用户选择 LatentSync 模型并点击生成
- **THEN** 系统使用 LatentSync 扩散模型生成高质量唇形同步视频（质量最高但速度最慢）

#### Scenario: 生成进度反馈
- **WHEN** 视频正在生成中
- **THEN** 前端实时显示生成进度百分比和当前步骤（如"正在加载 ONNX 推理会话"、"正在提取音频特征"、"正在生成唇形"、"正在合成视频"）

### Requirement: GPU 多平台支持（DirectML 优先）
系统 SHALL 通过 GPU 抽象层支持 AMD（DirectML/ROCm）、NVIDIA（DirectML/CUDA）、Intel（DirectML）显卡，Wav2Lip 推理优先使用 DirectML provider；自动检测可用 provider 并按优先级回退。

#### Scenario: AMD GPU 环境（DirectML）
- **WHEN** 系统检测到 AMD GPU 且已安装 onnxruntime-directml
- **THEN** Wav2Lip 推理使用 DirectML EP；日志记录 GPU 型号、DirectML 设备 ID、显存使用

#### Scenario: NVIDIA GPU 环境（DirectML）
- **WHEN** 系统检测到 NVIDIA GPU 且已安装 onnxruntime-directml
- **THEN** Wav2Lip 推理使用 DirectML EP；日志记录 GPU 型号、DirectML 设备 ID、显存使用

#### Scenario: Intel 核显/Intel Arc 环境
- **WHEN** 系统检测到 Intel GPU
- **THEN** Wav2Lip 推理使用 DirectML EP；日志记录 Intel 设备信息

#### Scenario: 无 GPU / 驱动未装环境
- **WHEN** 系统未检测到可用 GPU 或 onnxruntime-directml 不可用
- **THEN** Wav2Lip 推理回退到 CPUExecutionProvider，日志明确警告性能下降；SadTalker / LatentSync 继续按各自 PyTorch 路径（CUDA/ROCm/CPU）执行

### Requirement: 详细后端日志
系统 SHALL 在所有关键操作中记录详细日志，包括请求参数、处理步骤、耗时、错误堆栈等，确保任何问题都能被追踪和定位。

#### Scenario: 视频生成日志
- **WHEN** 用户发起视频生成请求
- **THEN** 系统记录：请求 ID、用户参数（模型选择、音频时长、形象 ID）、ONNX 会话创建、provider 选择、每个处理步骤的开始/结束时间、显存/内存使用、最终结果状态

#### Scenario: 错误追踪日志
- **WHEN** 任何处理步骤发生错误
- **THEN** 系统记录完整的错误堆栈、输入参数快照、当前处理阶段、ONNX provider 信息，并返回用户友好的错误提示

### Requirement: 美观的前端界面
系统 SHALL 提供现代化、美观的 Web 界面，包含音频波形可视化、视频预览播放器、模型选择卡片、生成进度动画等。

#### Scenario: 首页体验
- **WHEN** 用户打开应用首页
- **THEN** 看到清晰的操作流程引导（上传音乐 → 选择高潮 → 选择形象 → 选择模型 → 生成视频），界面采用深色主题，视觉层次分明

#### Scenario: 音频波形交互
- **WHEN** 音乐上传完成
- **THEN** 显示音频波形图，高潮区间高亮标注，用户可拖拽调整区间，播放预览截取片段

#### Scenario: 模型选择卡片
- **WHEN** 用户进入模型选择
- **THEN** 看到三张对比卡片：Wav2Lip-ONNX（默认，速度快、跨平台）、SadTalker（3DMM 头部动作）、LatentSync（扩散模型，质量最高），明确标注推荐项

## MODIFIED Requirements
无（新项目）。

## REMOVED Requirements
无（新项目）。注：原 Wav2Lip PyTorch 推理路径被 Wav2Lip-ONNX + DirectML 路径替换，但 SadTalker/LatentSync 的 PyTorch 路径保留。
