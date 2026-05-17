# VoiceType - AI 语音输入工具

Ubuntu 环境下的 AI 语音转文字工具，支持阿里云 Paraformer 和本地 faster-whisper 模型。

## 功能特性

- 🎤 实时语音输入转文字
- ⌨️ 自动粘贴到光标位置
- 🔥 全局快捷键触发
- 🌐 支持阿里云 Paraformer（云端）
- 💻 支持 faster-whisper（本地离线）
- 🎨 暗黑极简 GUI 界面
- 📊 实时转写浮窗显示

## 安装

### 方式一：使用 deb 包安装（推荐）

下载并安装 deb 包：

```bash
# 从 GitHub Releases 下载最新版本
wget https://github.com/hongyan199048/voice_typing/releases/download/v1.0.0/voice-typing_1.0.0_amd64.deb

# 安装
sudo dpkg -i voice-typing_1.0.0_amd64.deb

# 如果有依赖问题，运行：
sudo apt-get install -f
```

安装后可直接从应用菜单启动，或命令行运行 `voice-typing`

### 方式二：从源码安装

```bash
git clone https://github.com/hongyan199048/voice_typing.git
cd voice_typing
pip install -r requirements.txt
python main.py
```

## 使用

```bash
python main.py
```

首次运行会显示设置窗口：

1. **选择引擎**：阿里云（需 API Key）或本地模型
2. **配置 API**：如使用阿里云，输入 DashScope API Key
3. **下载模型**：如使用本地模式，选择模型大小并下载
4. **设置快捷键**：点击"录制快捷键"按钮，按下组合键

## 快捷键使用

1. 按住快捷键（默认 Ctrl+Alt+V）开始录音
2. 屏幕底部显示绿色指示灯和实时转写
3. 松开快捷键停止录音
4. 文字自动粘贴到光标位置

## 国内用户加速

### 方案一：使用 Hugging Face 镜像（推荐）

faster-whisper 模型托管在 Hugging Face，国内访问较慢。可使用国内镜像加速：

```bash
export HF_ENDPOINT=https://hf-mirror.com
python main.py
```

### 方案二：手动下载模型

如果镜像仍然无法访问，可手动下载模型：

1. 通过 VPN 访问 Hugging Face 下载模型文件
2. 模型地址：https://huggingface.co/guillaumekln/faster-whisper-large-v2
3. 下载后放置到：`~/.cache/voice_typing/models/`
4. 或使用阿里云 Paraformer 引擎（无需下载模型，仅需 API Key）

### 方案三：使用阿里云引擎（无需 VPN）

推荐国内用户直接使用阿里云 Paraformer 引擎：
- 无需下载大模型文件
- 识别速度快，准确率高
- 申请 DashScope API Key：https://dashscope.console.aliyun.com/

## 依赖

- PyQt5 - GUI 框架
- pyaudio - 音频采集
- dashscope - 阿里云语音 SDK
- faster-whisper - 本地语音识别
- pynput - 全局快捷键
- xclip + xdotool - 剪贴板和键盘模拟

## 配置文件

配置保存在 `~/.config/voice_typing/config.json`

## 故障排查

**问题：快捷键不响应**
- 检查是否与系统快捷键冲突
- 尝试更换快捷键组合

**问题：下载模型失败**
- 检查网络连接
- 使用 HF_ENDPOINT 镜像加速
- 手动下载模型到 `~/.cache/voice_typing/models/`

**问题：录音无声音**
- 检查麦克风权限
- 运行 `arecord -l` 确认音频设备

## 许可

MIT License
