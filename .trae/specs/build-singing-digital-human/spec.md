# 会唱歌的数字人 Spec

## Why
用户拥有音乐但无法让数字人演唱出来。需要一个系统，上传本地音乐后自动截取高潮部分，由数字人音画同步、口型一致地演唱出来，呈现美观的交互界面。

## What Changes
- 构建全栈Web应用：Python后端（FastAPI）+ 现代前端
- 集成Wav2Lip、SadTalker、LatentSync三种开源唇形同步模型，用户可切换
- 实现音乐上传与高潮自动检测（pychorus + librosa）
- 实现GPU抽象层，支持AMD ROCm / NVIDIA CUDA / Intel（预留接口）
- 提供数字人形象管理（上传/选择参考图片或视频）
- 实现详细的后端日志系统，覆盖所有关键操作和错误
- 构建美观的前端界面，包含音频波形可视化、视频预览等

## Impact
- Affected specs: 新项目，无已有spec
- Affected code: 全新项目

## ADDED Requirements

### Requirement: 音乐上传与高潮检测
系统SHALL提供音乐文件上传功能，支持MP3/WAV/M4A/FLAC格式，上传后自动检测歌曲高潮段落，用户可预览高潮片段并手动调整起止时间。

#### Scenario: 上传音乐并自动检测高潮
- **WHEN** 用户上传一个音乐文件
- **THEN** 系统解析音频，使用pychorus库检测高潮段落，返回高潮起止时间，并在前端波形图上高亮标注

#### Scenario: 手动调整高潮区间
- **WHEN** 用户对自动检测的高潮区间不满意
- **THEN** 用户可在波形图上拖拽调整起止时间，或手动输入时间，系统实时预览截取片段

### Requirement: 数字人形象管理
系统SHALL支持用户上传参考图片（单张人脸正面照）或参考视频作为数字人形象源，并提供预设形象供选择。

#### Scenario: 上传自定义形象
- **WHEN** 用户上传一张正面人脸照片或一段包含人脸的短视频
- **THEN** 系统验证图片/视频中是否包含可识别人脸，验证通过后保存为可用形象

#### Scenario: 选择预设形象
- **WHEN** 用户从预设形象列表中选择一个
- **THEN** 系统加载该预设形象的预览图和必要数据

### Requirement: 唇形同步视频生成
系统SHALL支持三种唇形同步模型（Wav2Lip、SadTalker、LatentSync），用户可选择模型，系统将截取的高潮音频与数字人形象合成口型同步的演唱视频。

#### Scenario: 使用Wav2Lip生成视频
- **WHEN** 用户选择Wav2Lip模型并点击生成
- **THEN** 系统使用Wav2Lip模型将高潮音频与数字人形象合成唇形同步视频，Wav2Lip为默认模型（速度最快、兼容性最好）

#### Scenario: 使用SadTalker生成视频
- **WHEN** 用户选择SadTalker模型并点击生成
- **THEN** 系统使用SadTalker模型生成3DMM驱动的说话人脸动画视频，支持头部姿态和表情控制

#### Scenario: 使用LatentSync生成视频
- **WHEN** 用户选择LatentSync模型并点击生成
- **THEN** 系统使用LatentSync扩散模型生成高质量唇形同步视频（质量最高但速度最慢）

#### Scenario: 生成进度反馈
- **WHEN** 视频正在生成中
- **THEN** 前端实时显示生成进度百分比和当前步骤（如"正在提取音频特征"、"正在生成唇形"、"正在合成视频"）

### Requirement: GPU多平台支持
系统SHALL通过GPU抽象层支持AMD（ROCm）、NVIDIA（CUDA）和Intel（预留接口）显卡，自动检测可用GPU并选择对应后端。

#### Scenario: AMD GPU环境
- **WHEN** 系统检测到AMD GPU且已安装ROCm
- **THEN** 系统使用PyTorch ROCm版本进行推理，日志记录GPU型号和ROCm版本

#### Scenario: NVIDIA GPU环境
- **WHEN** 系统检测到NVIDIA GPU且已安装CUDA
- **THEN** 系统使用PyTorch CUDA版本进行推理，日志记录GPU型号和CUDA版本

#### Scenario: 无GPU环境
- **WHEN** 系统未检测到可用GPU
- **THEN** 系统降级为CPU推理，日志警告性能将显著下降

### Requirement: 详细后端日志
系统SHALL在所有关键操作中记录详细日志，包括请求参数、处理步骤、耗时、错误堆栈等，确保任何问题都能被追踪和定位。

#### Scenario: 视频生成日志
- **WHEN** 用户发起视频生成请求
- **THEN** 系统记录：请求ID、用户参数（模型选择、音频时长、形象ID）、每个处理步骤的开始/结束时间、GPU内存使用情况、最终结果状态

#### Scenario: 错误追踪日志
- **WHEN** 任何处理步骤发生错误
- **THEN** 系统记录完整的错误堆栈、输入参数快照、当前处理阶段，并返回用户友好的错误提示

### Requirement: 美观的前端界面
系统SHALL提供现代化、美观的Web界面，包含音频波形可视化、视频预览播放器、模型选择卡片、生成进度动画等。

#### Scenario: 首页体验
- **WHEN** 用户打开应用首页
- **THEN** 看到清晰的操作流程引导（上传音乐 → 选择高潮 → 选择形象 → 生成视频），界面采用深色主题，视觉层次分明

#### Scenario: 音频波形交互
- **WHEN** 音乐上传完成
- **THEN** 显示音频波形图，高潮区间高亮标注，用户可拖拽调整区间，播放预览截取片段

## MODIFIED Requirements
无（新项目）

## REMOVED Requirements
无（新项目）
