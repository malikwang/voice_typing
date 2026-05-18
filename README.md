# VoiceType - AI 语音输入工具

Ubuntu 环境下的 AI 语音转文字工具，支持阿里云 Paraformer 和本地 faster-whisper 模型。

## 功能特性

- 🎤 实时语音输入转文字
- ⌨️ 自动粘贴到光标位置
- 🔥 全局快捷键触发（默认 Ctrl+Alt+V）
- 🌐 支持阿里云 Paraformer（云端）
- 💻 支持 faster-whisper（本地离线）
- 🎨 暗黑极简 GUI 界面
- 📊 实时转写浮窗显示

## 安装

### 方式一：deb 包安装（推荐）

从 [GitHub Releases](https://github.com/hongyan199048/voice_typing/releases) 下载最新版本：

```bash
wget https://github.com/hongyan199048/voice_typing/releases/download/v1.0.0/voice-typing_1.0.0_amd64.deb
sudo dpkg -i voice-typing_1.0.0_amd64.deb
sudo apt-get install -f  # 如有依赖问题
```

安装后从应用菜单启动，或命令行运行 `voice-typing`

### 方式二：从源码运行

```bash
git clone https://github.com/hongyan199048/voice_typing.git
cd voice_typing
pip install -r requirements.txt
python main.py
```

## 使用

首次运行会显示设置窗口：

1. **选择引擎**：阿里云（需 API Key）或本地模型
2. **配置 API**：使用阿里云时，输入 [DashScope API Key](https://dashscope.console.aliyun.com/)
3. **下载模型**：使用本地模式时，选择模型大小（tiny/base/small）并下载
4. **设置快捷键**：点击"录制快捷键"，按下组合键

**语音输入**：
1. 按住快捷键开始录音
2. 屏幕底部显示实时转写
3. 松开快捷键，文字自动粘贴到光标位置

## 注意事项

- **本地模型下载**：faster-whisper 模型托管在 Hugging Face，国内访问需要 VPN
- **推荐方案**：国内用户建议使用阿里云 Paraformer 引擎，无需下载模型，识别速度快

## 故障排查

**快捷键不响应**
- 检查是否与系统快捷键冲突
- 尝试更换快捷键组合

**模型下载失败**
- 确保网络可访问 Hugging Face（可能需要 VPN）
- 或切换到阿里云引擎

**录音无声音**
- 检查麦克风权限
- 运行 `arecord -l` 确认音频设备

## 配置文件

配置保存在 `~/.config/voice_typing/config.json`

## 许可

MIT License
