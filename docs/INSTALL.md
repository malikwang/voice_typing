# VoiceType 安装说明

## 系统要求

- Ubuntu 22.04 或更高版本（x86_64 架构）
- Python 3.8+
- 至少 2GB 可用磁盘空间（用于本地模型）

## 安装步骤

### 方法 1：使用 deb 包安装（推荐）

1. 下载 deb 包：
```bash
wget https://github.com/hongyan199048/voice_typing/releases/download/v1.0.0/voice-typing_1.0.0_amd64.deb
```

2. 安装：
```bash
sudo dpkg -i voice-typing_1.0.0_amd64.deb
```

3. 如果出现依赖问题，运行：
```bash
sudo apt-get install -f
```

4. 启动应用：
```bash
voice-typing
```

或者在应用菜单中搜索 "VoiceType"。

### 方法 2：从源码安装

1. 克隆仓库：
```bash
git clone https://github.com/hongyan199048/voice_typing.git
cd voice_typing
```

2. 安装系统依赖：
```bash
sudo apt-get install python3-pyqt5 python3-pyaudio xclip xdotool
```

3. 安装 Python 依赖：
```bash
pip3 install -r requirements.txt
```

4. 运行：
```bash
python3 main.py
```

## 使用说明

### 首次使用

1. 启动应用后，屏幕下方会出现一个小窗口（绿色圆球）
2. 点击设置图标配置语音引擎：
   - **阿里云模式**：需要填写 DashScope API Key
   - **本地模式**：选择模型大小并下载（推荐 base 模型）

### 语音输入

1. 打开任意文本编辑器或输入框
2. 将光标放在想要输入文字的位置
3. 按住 **Ctrl+Alt+S**，圆球变红并显示波形动画
4. 开始说话
5. 松开快捷键，识别结果会自动粘贴到光标处

### 状态指示

- **绿色圆球**：待机状态
- **红色圆球 + 波形**：正在录音
- **文字显示**：识别完成，即将粘贴

## 配置文件

配置文件位于：`~/.config/voice_typing/config.json`

可手动编辑以下选项：
```json
{
  "engine": "local",           // "alibaba" 或 "local"
  "alibaba_api_key": "",       // 阿里云 API Key
  "local_model": "base",       // "tiny", "base", "small"
  "hotkey": ["ctrl", "alt", "s"]  // 快捷键组合
}
```

## 卸载

```bash
sudo dpkg -r voice-typing
```

## 常见问题

### 1. 快捷键不响应
- 检查是否与其他应用的快捷键冲突
- 在设置中重新录制快捷键

### 2. 本地模型下载失败
- 检查网络连接
- 确保有足够的磁盘空间
- 手动下载模型到 `~/.cache/huggingface/hub/`

### 3. 粘贴功能不工作
- 确保已安装 xclip 和 xdotool：
  ```bash
  sudo apt-get install xclip xdotool
  ```

### 4. 录音没有声音
- 检查麦克风权限
- 在系统设置中选择正确的输入设备

## 技术支持

- GitHub Issues: https://github.com/hongyan199048/voice_typing/issues
- 项目主页: https://github.com/hongyan199048/voice_typing

## 许可证

MIT License
