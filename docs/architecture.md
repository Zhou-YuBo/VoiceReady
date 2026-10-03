# VoiceReady 架构基线

## 一句话

一个产品，两个工作台，共享一个项目数据库。

工作台分别是“素材准备”和“RVC 实验室”。

## 三套目录

### 源码仓库

```text
VoiceReady/
├── apps/
│   ├── desktop/              # Tauri、Rust
│   ├── frontend/             # Vue 3、TypeScript
│   └── kernel/               # Python 应用内核入口
├── packages/
│   ├── py-core/              # 领域模型、数据库、任务协调
│   ├── py-audio/             # 音频基础能力
│   ├── py-voice-prep/        # TTS/RVC 共用素材准备
│   ├── py-tts-prep/          # ASR、官方文本、TTS 校对
│   └── py-rvc-lab/           # RVC 分析与推理辅助
├── contracts/                # Rust、Python、worker 共用协议
├── runners/                  # 独立 worker 入口
├── adapters/                 # 外部工具适配器
├── modules/                  # 可选安装模块定义
├── installers/               # 安装包和运行时清单
├── tests/
└── docs/
```

### 安装目录

```text
VoiceReadyInstall/
├── VoiceReady.exe
├── resources/
├── modules/
├── runtimes/
└── adapters/
```

外部 GPT-SoVITS、Applio 和其他训练包不放进主安装目录。

### 用户项目目录

```text
MyVoiceProject/
├── project.vrproj
└── voiceready/
    ├── db/project.sqlite
    ├── media/voice/sources/
    ├── media/voice/derivatives/
    ├── media/voice/segments/
    ├── media/songs/sources/
    ├── media/models/imported/
    ├── work/jobs/
    ├── views/review/
    ├── views/tts/
    ├── views/rvc/
    ├── exports/tts/
    ├── exports/rvc/
    ├── exports/reports/
    ├── cache/
    └── logs/
```

## 模块安装

```text
TTS 素材 = core + voice-prep + tts-prep
RVC 素材 = core + voice-prep
RVC 推理 = core + rvc-lab
完整安装 = core + voice-prep + tts-prep + rvc-lab
```

所有模块共享一个项目数据库。

模块只增加自己的表、任务、worker 和页面。

卸载模块不能删除项目数据。

## 进程关系

```text
Vue 前端
  ↓
Tauri/Rust 桌面壳
  ↓ 版本化 IPC
Python 应用内核
  ↓
独立 Python worker 或外部适配器
```

第一版不把 Python 嵌入 Rust 进程。

## 当前未初始化的部分

- Rust workspace 和 Tauri 工程
- Vue 工程和前端依赖
- Python workspace 和运行时锁定
- SQLite schema 和迁移
- worker 协议具体字段
- 安装器实现
