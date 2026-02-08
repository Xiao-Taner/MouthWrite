# MouthWrite

MouthWrite 是一款 Windows 端 AI 语音输入法。按住快捷键说话，松开后自动完成语音转录、大模型文本优化，并将结果粘贴到当前光标所在的输入框中。还可一键调用大模型将优化后的文本翻译为目标语言。

## 演示

![MouthWrite 演示](assets/screenshots.gif)

## 功能特性

- **语音转文字** — 支持本地 vLLM 部署的 [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR) 以及阿里云 DashScope 在线 API（`qwen3-asr-flash`），实时流式转录
- **大模型文本优化** — 调用 DeepSeek 等 OpenAI 兼容 API，自动去除语气词、修正数字/术语、规范中英混排
- **一键翻译** — 优化完成后可点击翻译按钮，将文本翻译为可配置的目标语言
- **自动粘贴** — 最终文本自动复制到剪贴板并模拟 `Ctrl+V` 粘贴到当前焦点输入框
- **历史记录** — 每次对话自动保存到本地，可在设置页面浏览和复制，历史记录还会作为上下文辅助大模型优化
- **提示音** — 按下 / 松开快捷键时播放开始与结束提示音
- **全局快捷键** — 默认长按右 Alt 触发，可在设置中自定义
- **系统托盘** — 双击运行后常驻托盘，右键可打开设置或退出
- **深色主题** — 底部居中浮窗，`#272727` 深色背景，分段显示转录 / 优化 / 翻译结果
- **可打包为独立 EXE** — 通过 PyInstaller 打包为单文件 Windows 应用

## 技术架构

![技术架构](assets/TF.png)

**主要技术栈：**

| 组件 | 技术 |
|------|------|
| 编程语言 | Python 3.12 |
| GUI 框架 | PySide6 (Qt for Python) |
| 音频采集 | sounddevice + numpy |
| 全局热键 | pynput |
| HTTP 客户端 | httpx (SSE 流式) |
| ASR 模型 | Qwen3-ASR (vLLM / DashScope API) |
| LLM | DeepSeek 或其他 OpenAI 兼容 API |
| 打包工具 | PyInstaller |

## 目录结构

```
MouthWrite/
├── main.py                 # 应用入口
├── config.py               # 配置管理（单例，JSON 持久化）
├── utils.py                # 通用工具（资源路径兼容 PyInstaller）
├── requirements.txt        # Python 依赖
├── MouthWrite.spec         # PyInstaller 打包配置
│
├── core/                   # 核心业务逻辑
│   ├── controller.py       # 调度中枢：串联热键→录音→ASR→LLM→粘贴
│   ├── hotkey.py           # 全局热键监听（RAlt / AltGr）
│   ├── audio.py            # 麦克风录音（16kHz PCM）
│   ├── asr_client.py       # ASR 流式调用（自动适配 vLLM / DashScope）
│   ├── llm_client.py       # LLM 文本优化 & 翻译（SSE 流式）
│   └── history.py          # 本地历史记录管理
│
├── gui/                    # 图形界面
│   ├── main_window.py      # 底部浮窗（转录/优化/翻译分段显示）
│   ├── settings_dialog.py  # 设置对话框（含历史记录页面）
│   ├── tray_icon.py        # 系统托盘图标
│   ├── start.mp3           # 开始录音提示音
│   └── end.mp3             # 结束录音提示音
│
├── assets/
│   └── icon.ico            # 应用图标
│
├── scripts/
│   └── gen_icon.py         # 图标生成脚本（PySide6 绘制）
│
└── test/                   # 测试脚本
    ├── test_asr.py         # ASR 本地 vLLM 测试
    └── test_flash.py       # DashScope qwen3-asr-flash 测试
```

## 安装指南

### 环境要求

- Windows 10/11
- Python 3.12+（推荐使用 [uv](https://docs.astral.sh/uv/) 管理环境）
- 一个可用的 ASR 服务（二选一）：
  - 本地：在 WSL2 / Linux 上通过 vLLM 部署 [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR)
  - 在线：阿里云 DashScope API（模型 `qwen3-asr-flash`）
- 一个 LLM API Key（如 [DeepSeek](https://platform.deepseek.com/)）用于文本优化和翻译

### 从源码运行

```bash
# 1. 克隆仓库
git clone https://github.com/Xiao-Taner/MouthWrite.git
cd MouthWrite

# 2. 创建虚拟环境并安装依赖（使用 uv）
uv venv --python 3.12
.venv\Scripts\activate     # Windows
uv pip install -r requirements.txt

# 或者使用 pip
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. 运行
python main.py
```

首次启动后，右键托盘图标 → **设置**，填入：
- **语音识别** 页：ASR 服务地址、模型名称、API Key
- **大模型** 页：LLM 服务地址、模型名称、API Key
- **翻译** 页：目标语言（默认 English）

配置文件保存在 `%APPDATA%\MouthWrite\config.json`。

### ASR 服务部署（本地 vLLM 方案）

如果你选择本地部署 ASR 模型，需要在 WSL2 或 Linux 上安装 vLLM 并启动服务：

```bash
# 在 WSL2 / Linux 中
pip install -U qwen-asr[vllm]
qwen-asr-serve Qwen/Qwen3-ASR-1.7B --gpu-memory-utilization 0.8 --host 0.0.0.0 --port 8000
```

然后在 MouthWrite 设置中将 ASR 服务地址设为 `http://localhost:8000/v1`。

### ASR 服务（DashScope 在线方案）

如果不想本地部署，可以使用阿里云 DashScope 的在线 API：

1. 前往 [阿里云百炼](https://help.aliyun.com/zh/model-studio/get-api-key) 获取 API Key
2. 在 MouthWrite 设置中填入：
   - ASR 服务地址：`https://dashscope.aliyuncs.com/compatible-mode/v1`
   - 模型名称：`qwen3-asr-flash`
   - API Key：你的 DashScope API Key

## 打包为 EXE

```bash
# 1. 安装 PyInstaller
pip install pyinstaller

# 2. 执行打包
pyinstaller MouthWrite.spec

# 3. 生成的可执行文件
dist/MouthWrite.exe
```

打包后为单个 `.exe` 文件，双击即可运行。首次启动会自动在 `%APPDATA%\MouthWrite\` 创建配置文件，用户通过设置页面填入自己的 API Key 即可使用。

> 如需自定义应用图标，替换 `assets/icon.ico` 后重新打包即可。也可运行 `python scripts/gen_icon.py` 重新生成默认图标。

## 使用方法

1. 双击运行 `MouthWrite.exe`（或 `python main.py`），程序常驻系统托盘
2. **长按右 Alt 键**开始说话（听到开始提示音），**松开**结束录音（听到结束提示音）
3. 自动完成：语音转录 → 大模型优化 → 复制到剪贴板 → 粘贴到当前输入框
4. 如需翻译，点击浮窗右下角的 **翻译** 按钮
5. 点击窗口外部或按任意键关闭浮窗

## 许可证

MIT License
