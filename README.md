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

```bash
cd /home/admin123/Development/voice_typing
pip install -r requirements.txt
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

如果 Hugging Face 下载慢，设置镜像：

```bash
export HF_ENDPOINT=https://hf-mirror.com
python main.py
```

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
