# VoiceType - AI 语音输入工具

Ubuntu 环境下的实时语音转文字工具，基于小米 ASR_Streaming 模型，支持全局快捷键触发，自动粘贴到光标位置。

## 功能特性

- 按住快捷键录音，松开自动停止并粘贴
- 实时转写浮窗显示（边说边出字）
- 基于小米 Mify 平台 ASR_Streaming 流式识别
- 暗黑极简 GUI + 系统托盘

## 安装

### 系统依赖

```bash
sudo apt install portaudio19-dev xclip xdotool
```

### Python 依赖

```bash
git clone https://github.com/malikwang/voice_typing.git
cd voice_typing
pip install -r requirements.txt
```

### 运行

```bash
python main.py
```

## 使用

1. 首次运行在设置窗口输入小米 Mify API Key
2. 按住快捷键（默认 Ctrl+Alt+V）开始录音
3. 松开快捷键，1.5 秒后自动停止并粘贴识别结果

> 按住不到 0.5 秒不会触发录音，防止误触。

## 快捷键

- 默认：`Ctrl+Alt+V`（可在设置中修改）
- 模式：按住录音，松开停止（hold 模式）
- 支持单键或组合键

## API Key 获取

1. 打开 [Mify 平台](https://mify.mioffice.cn/gateway?tab=api-key)
2. 创建个人 API Key
3. 在设置窗口粘贴

## 配置文件

`~/.config/voice_typing/config.json`

```json
{
  "engine": "mimo",
  "mimo_api_key": "sk-xxx",
  "hotkey": ["ctrl", "alt", "v"]
}
```

## 故障排查

**前几秒无法识别**
- 麦克风增益过高导致削波，应用会自动设为 35%
- 手动检查：`pactl get-source-volume @DEFAULT_SOURCE@`

**快捷键不响应**
- 检查是否与系统快捷键冲突
- 需要 X11 环境（Wayland 可能不兼容）

**录音无声音**
- `arecord -l` 确认音频设备
- 确保 PulseAudio 正常运行

## 技术栈

| 组件 | 技术 |
|------|------|
| GUI | PyQt5 |
| 音频采集 | pyaudio (16kHz 16bit mono) |
| 全局快捷键 | pynput |
| ASR | 小米 ASR_Streaming (WebSocket) |
| 粘贴 | xclip + pynput |

## 许可

MIT License
