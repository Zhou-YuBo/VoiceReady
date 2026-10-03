# VoiceReady

VoiceReady 为 TTS 素材准备和 RVC 推理分析提供统一工作台。

当前仓库只完成目录和架构初始化。

尚未安装运行时，也尚未写入业务代码。

## 技术栈

- Tauri + Rust：桌面壳、系统边界和进程生命周期
- Vue 3 + TypeScript：界面和交互
- Python：应用内核、AI 工作流和音频处理
- SQLite：项目事实来源

## 模块

- `voice-prep`：TTS、RVC 共用的素材准备
- `tts-prep`：ASR、官方文本和 TTS 校对
- `rvc-lab`：歌曲分析、pitch 推荐、推理和结果检查

## 当前阶段

先冻结目录边界，再分别讨论 Rust、Vue 和 Python 的初始化方式。

不要在没有确认运行时方案前安装大型依赖。

## 设计记录

- `docs/architecture.md`：当前架构和目录约束
- `contracts/`：Rust、Python、worker 共用协议
- `modules/`：可选择安装的模块清单
