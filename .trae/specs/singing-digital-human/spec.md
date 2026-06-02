# 会唱歌的数字人 Spec

## Why
用户拥有本地音乐但无法让数字人演唱出来。需要一个端到端 Web 应用：上传音乐后自动检测高潮部分，截取片段由数字人音画同步、口型一致地演唱出来，呈现美观的交互界面。模型层只保留 Wav2Lip-ONNX（ONNX Runtime + DirectML），通过 DirectML 跨平台覆盖 AMD/NVIDIA/Intel GPU，CPU 自动回滚，部署更轻量、兼容性更好。

## What Changes
- 构建全栈 Web 应用：Python 后端（FastAPI）+ 现代前端（React + Vite + TailwindCSS）
- 集成 Wav2Lip-ONNX 唇形同步模型（唯一模型）：使用 ONNX Runtime + DirectML 在 AMD/NVIDIA/Intel GPU 上推理，CPU 兜底
- 音乐上传与高潮自动检测（pychorus + librosa），前端波形可视化与区间拖拽
- GPU 抽象层，支持 AMD（DirectML/ROCm）、NVIDIA（DirectML/CUDA）、Intel（DirectML），无 GPU 时 CPU 回退
- 数字人形象管理：自定义上传（图片/视频，含人脸检测）+ 预设形象
- 详细结构化后端日志：请求 ID、阶段耗时、错误堆栈、GPU/Provider 信息
- 美观深色主题前端，含音频波形、视频预览、生成进度动画
- **BREAKING（针对原三模型方案）**：删除 SadTalker、LatentSync 两种模型及其相关代码/权重/任务；模型调度器简化为 Wav2Lip-ONNX 单一路径

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
系统 SHALL 使用 Wav2Lip 的 ONNX 导出模型，通过 ONNX Runtime + DirectML 在多平台 GPU 上推理，将截取的高潮音频与数字人形象合成口型同步的演唱视频。

#### Scenario: 使用 Wav2Lip-ONNX 生成视频
- **WHEN** 用户点击生成按钮
- **THEN** 系统使用 ONNX Runtime 加载 wav2lip.onnx 权重，DirectML provider 优先（CPU 兜底），将高潮音频与数字人形象合成唇形同步视频；记录推理设备、provider、耗时与输出分辨率

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
- **THEN** Wav2Lip 推理回退到 CPUExecutionProvider，日志明确警告性能下降

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
