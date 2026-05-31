# Tasks

- [x] Task 1: 项目初始化与基础架构搭建
  - [x] SubTask 1.1: 创建项目目录结构（backend/、frontend/、models/、data/）
  - [x] SubTask 1.2: 初始化Python后端项目（FastAPI + pyproject.toml + 依赖管理）
  - [x] SubTask 1.3: 初始化前端项目（React + Vite + TailwindCSS）
  - [x] SubTask 1.4: 配置后端日志系统（结构化日志，请求ID追踪）
  - [x] SubTask 1.5: 配置CORS和前后端联调环境

- [x] Task 2: GPU抽象层与设备检测
  - [x] SubTask 2.1: 实现GPU检测模块（自动识别AMD/NVIDIA/CPU）
  - [x] SubTask 2.2: 实现GPU抽象接口（统一device管理、内存监控）
  - [x] SubTask 2.3: 编写GPU检测和切换的日志记录

- [x] Task 3: 音乐上传与高潮检测
  - [x] SubTask 3.1: 实现音乐文件上传API（支持MP3/WAV/M4A/FLAC）
  - [x] SubTask 3.2: 集成pychorus实现高潮自动检测
  - [x] SubTask 3.3: 实现音频截取API（根据起止时间截取片段）
  - [x] SubTask 3.4: 实现音频波形数据生成API（供前端可视化）

- [x] Task 4: 数字人形象管理
  - [x] SubTask 4.1: 实现形象上传API（图片/视频，含人脸检测验证）
  - [x] SubTask 4.2: 实现预设形象管理（内置2-3个默认形象）
  - [x] SubTask 4.3: 实现形象列表查询和预览API

- [x] Task 5: 唇形同步模型集成 - Wav2Lip（默认模型）
  - [x] SubTask 5.1: 下载并配置Wav2Lip预训练模型权重
  - [x] SubTask 5.2: 封装Wav2Lip推理接口（输入：音频+形象，输出：视频）
  - [x] SubTask 5.3: 实现Wav2Lip的AMD ROCm兼容处理
  - [x] SubTask 5.4: 实现视频生成进度回调机制

- [x] Task 6: 唇形同步模型集成 - SadTalker
  - [x] SubTask 6.1: 下载并配置SadTalker预训练模型权重
  - [x] SubTask 6.2: 封装SadTalker推理接口（支持3DMM参数、头部姿态控制）
  - [x] SubTask 6.3: 实现SadTalker的AMD ROCm兼容处理

- [x] Task 7: 唇形同步模型集成 - LatentSync
  - [x] SubTask 7.1: 下载并配置LatentSync预训练模型权重
  - [x] SubTask 7.2: 封装LatentSync推理接口（扩散模型推理流程）
  - [x] SubTask 7.3: 实现LatentSync的AMD ROCm兼容处理

- [x] Task 8: 统一模型调度与视频生成API
  - [x] SubTask 8.1: 实现模型调度器（统一接口，根据用户选择调用对应模型）
  - [x] SubTask 8.2: 实现视频生成API（POST /api/generate，含参数校验）
  - [x] SubTask 8.3: 实现生成任务状态查询API（进度、结果、错误信息）
  - [x] SubTask 8.4: 实现生成结果视频的存储和下载API

- [x] Task 9: 前端界面开发
  - [x] SubTask 9.1: 搭建页面布局和路由（首页、生成页、历史记录页）
  - [x] SubTask 9.2: 实现音乐上传组件（拖拽上传、格式校验）
  - [x] SubTask 9.3: 实现音频波形可视化组件（WaveSurfer.js集成、高潮标注、区间拖拽）
  - [x] SubTask 9.4: 实现数字人形象选择组件（预设卡片+自定义上传）
  - [x] SubTask 9.5: 实现模型选择组件（三模型对比卡片，含质量/速度说明）
  - [x] SubTask 9.6: 实现视频生成进度组件（进度条+步骤提示）
  - [x] SubTask 9.7: 实现视频播放器组件（预览+下载）
  - [x] SubTask 9.8: 实现深色主题和整体UI美化

- [x] Task 10: 端到端集成测试与优化
  - [x] SubTask 10.1: 编写完整流程集成测试（上传→检测→生成→播放）
  - [x] SubTask 10.2: 验证AMD 6700XT环境下的GPU推理
  - [x] SubTask 10.3: 性能优化（模型加载缓存、推理批处理）
  - [x] SubTask 10.4: 日志完整性验证（确保所有错误可追踪）

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 1]
- [Task 4] depends on [Task 1]
- [Task 5] depends on [Task 2]
- [Task 6] depends on [Task 2, Task 5]
- [Task 7] depends on [Task 2, Task 5]
- [Task 8] depends on [Task 5, Task 6, Task 7]
- [Task 9] depends on [Task 1]
- [Task 10] depends on [Task 8, Task 9]
- Task 3, Task 4, Task 5 可并行开发
- Task 9 的各子任务在前端框架搭建后可并行开发
