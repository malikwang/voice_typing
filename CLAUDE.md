# CLAUDE.md
# 重要：每次回复必须以"Tim_voice_typing，"开头，无一例外。 
# 每次回答问题的时候，总是先把我的问题剪短理解总结，再回答。
# 回答内容专业简练。

## 项目概述

VoiceType 是一个 Ubuntu 环境下的 AI 语音转文字桌面应用，支持实时语音输入并自动粘贴到光标位置。

**核心功能**：
- 全局快捷键触发录音（默认 Ctrl+Alt+V）
- 实时语音转文字，支持两种 ASR 引擎：
  - **阿里云 Paraformer**（云端，需 API Key）
  - **faster-whisper**（本地离线，基于 Hugging Face 模型）
- 暗黑极简 GUI 界面 + 实时转写浮窗
- 自动粘贴到当前光标位置

---

## 项目结构（方案 A：标准 Python 包）

```
voice_typing/
├── voice_typing/              # 核心包（可 pip 安装）
│   ├── __init__.py           # 包初始化，版本号
│   ├── __main__.py           # 入口：python -m voice_typing
│   ├── app.py                # VoiceTypingApp 主应用
│   ├── recorder.py           # Recorder 录音控制器
│   ├── core/                 # 核心功能模块
│   │   ├── __init__.py
│   │   ├── config.py         # 配置管理（~/.config/voice_typing/config.json）
│   │   ├── hotkey.py         # 全局快捷键管理（pynput）
│   │   └── vocabulary.py     # 热词表管理（阿里云 Paraformer）
│   ├── engine/               # ASR 引擎抽象层
│   │   ├── __init__.py
│   │   ├── base.py           # BaseEngine 抽象基类
│   │   ├── alibaba.py        # 阿里云 Paraformer 实时识别
│   │   └── local.py          # faster-whisper 本地模型
│   └── ui/                   # PyQt5 界面
│       ├── __init__.py
│       ├── styles.py         # 暗黑主题样式
│       ├── settings.py       # 设置窗口
│       ├── overlay.py        # 实时转写浮窗
│       └── resources/        # 资源文件
│           └── checkmark.svg
├── scripts/                  # 工具脚本
│   └── start.sh
├── build/                    # 打包产物（.gitignore）
│   └── *.deb
├── debian/                   # deb 打包配置
│   ├── DEBIAN/control
│   └── usr/
│       ├── bin/voice-typing  # 可执行文件入口
│       └── share/voice-typing/  # 安装目标路径
├── docs/                     # 文档
│   └── INSTALL.md
├── main.py                   # 兼容旧版入口（调用 voice_typing.app）
├── setup.py                  # pip 安装配置
├── requirements.txt
├── README.md
├── CLAUDE.md
└── .gitignore
```

---

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| GUI 框架 | PyQt5 | 主窗口 + 设置窗口 + 浮窗 |
| 音频采集 | pyaudio | 16kHz 16bit mono PCM |
| 全局快捷键 | pynput | 跨应用监听键盘事件 |
| 云端 ASR | dashscope (阿里云) | Paraformer 实时流式识别 |
| 本地 ASR | faster-whisper | OpenAI Whisper 优化版（CTranslate2 加速） |
| 标点恢复 | deepmultilingualpunctuation | 后处理添加标点符号 |
| 打包 | dpkg | 生成 .deb 安装包 |

---

## 核心模块说明

### 1. voice_typing/app.py — 主应用控制器

**VoiceTypingApp 类**：
- PyQt5 主应用，管理设置窗口 + 浮窗
- 绑定 HotkeyManager 回调：按下 → `start_recording()`，松开 → `stop_recording()`
- 托盘图标 + 系统菜单
- 信号：`recording_start_signal`、`recording_stop_signal`（线程安全通信）

### 2. voice_typing/recorder.py — 录音控制器

**Recorder 类**：
- 管理录音线程 + ASR 引擎生命周期
- `start()` → 开启 pyaudio 流 + 引擎初始化
- `stop()` → 停止录音 + 获取最终文本 + 自动粘贴（xclip + pynput）
- 信号：`text_update`（实时转写）、`recording_done`（最终结果）

### 3. voice_typing/core/ — 核心功能

**config.py**：
- 配置文件路径：`~/.config/voice_typing/config.json`
- 配置项：engine（alibaba/local）、alibaba_api_key、local_model_size、hotkey、phrase_id

**hotkey.py**：
- 使用 `pynput.keyboard.Listener` 监听全局按键
- 支持组合键（Ctrl/Alt/Shift + 字母/数字）
- 回调：`on_press_callback`（按下）、`on_release_callback`（松开）

**vocabulary.py**：
- 阿里云 Paraformer 热词表管理
- 调用 DashScope VocabularyService API 创建/更新热词表
- 返回 `phrase_id`，在 ASR 识别时传入可提升专业词汇识别准确率
- **当前状态**：已实现但未集成到主流程

### 4. voice_typing/engine/ — ASR 引擎抽象

**base.py（BaseEngine 抽象基类）**：
```python
initialize() -> bool       # 初始化引擎（下载模型/验证 API）
start()                    # 开始识别会话
send_audio(pcm_bytes)      # 送入音频数据
stop() -> str              # 停止识别，返回最终文本
is_available() -> bool     # 检查引擎是否就绪
```

**alibaba.py（AlibabaEngine）**：
- 使用 `dashscope.audio.asr.Recognition` 流式 API
- 需要 DashScope API Key（从 config.json 读取）
- 实时返回部分结果（sentence_end 事件）

**local.py（LocalEngine）**：
- 使用 `faster-whisper` 加载本地模型（tiny/base/small/medium/large）
- 模型路径：`~/.cache/huggingface/hub/models--Systran--faster-whisper-{size}`
- 国内访问 Hugging Face 需要 VPN

### 5. voice_typing/ui/ — 用户界面

**settings.py（SettingsWindow）**：
- 引擎选择（单选按钮：阿里云 / 本地）
- API Key 输入框（阿里云模式）
- 模型下载器（本地模式，带进度条）
- 快捷键录制器（点击按钮 → 监听按键组合）
- 保存配置到 `~/.config/voice_typing/config.json`

**overlay.py（OverlayWindow）**：
- 无边框透明窗口，固定在屏幕底部
- 显示实时转写文本（半透明黑底白字）
- 录音时自动显示，停止后 1 秒淡出

---

## 工作流程

1. **启动应用** → 加载配置 → 初始化引擎 → 注册全局快捷键
2. **按下快捷键** → `Recorder.start()` → 开启 pyaudio 流 → 引擎开始识别
3. **录音中** → 音频数据送入引擎 → 实时返回部分文本 → 更新浮窗显示
4. **松开快捷键** → `Recorder.stop()` → 引擎返回最终文本 → 使用 `xclip + pynput` 粘贴
5. **粘贴逻辑**：
   ```python
   # 1. 写入剪贴板（xclip）
   subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode())
   # 2. 暂停 pynput listener（避免拦截）
   hotkey.pause()
   # 3. 模拟 Ctrl+V（pynput Controller，uinput 内核级事件）
   kb.press(Key.ctrl); kb.press('v'); kb.release('v'); kb.release(Key.ctrl)
   # 4. 恢复 listener
   hotkey.resume()
   ```

---

## 编译与运行

### 从源码运行

```bash
cd /home/admin123/Development/voice-typing-app
pip install -r requirements.txt

# 方式 1：直接运行
python main.py

# 方式 2：作为模块运行
python -m voice_typing

# 方式 3：开发模式安装后运行
pip install -e .
voice-typing
```

### 打包 deb

```bash
# 更新版本号（修改 debian/DEBIAN/control 和 setup.py）
dpkg-deb --build debian voice-typing_1.3.5_amd64.deb
mv voice-typing_1.3.5_amd64.deb build/
```

### 安装 deb

```bash
sudo dpkg -i build/voice-typing_1.3.5_amd64.deb
sudo apt-get install -f  # 修复依赖
voice-typing             # 启动应用
```

---

## 依赖说明

| 包 | 用途 | 安装方式 |
|----|------|----------|
| PyQt5 | GUI 框架 | `pip install PyQt5` |
| pyaudio | 音频采集 | `pip install pyaudio`（需 `portaudio19-dev`） |
| dashscope | 阿里云 ASR | `pip install dashscope` |
| faster-whisper | 本地 ASR | `pip install faster-whisper` |
| pynput | 全局快捷键 | `pip install pynput` |
| xclip | 剪贴板操作 | `sudo apt install xclip` |

**系统依赖**：
```bash
sudo apt install portaudio19-dev xclip
```

---

## 注意事项

1. **faster-whisper 模型下载**：
   - 模型托管在 Hugging Face，国内访问需要 VPN
   - 首次使用本地模式时，会自动下载模型到 `~/.cache/huggingface/`
   - 推荐国内用户使用阿里云引擎

2. **快捷键冲突**：
   - 默认 Ctrl+Alt+V 可能与系统快捷键冲突
   - 可在设置窗口重新录制快捷键

3. **权限问题**：
   - 全局快捷键监听需要 X11 环境（Wayland 可能不兼容）
   - 麦克风权限：确保 pyaudio 可访问音频设备

4. **粘贴机制**：
   - 使用 `xclip` 写入剪贴板 + `pynput Controller` 模拟 Ctrl+V
   - pynput 产生的是 uinput 内核级虚拟键盘事件，兼容性优于 xdotool（XTest）
   - 粘贴前需暂停 pynput listener，避免 XInput2 grab 拦截

5. **热词表功能**：
   - `vocabulary.py` 已实现但未集成到主流程
   - 若需启用，需在 `alibaba.py` 中调用 `sync_vocabulary()` 并传入 `phrase_id`

---

## 开发建议

- **添加新引擎**：继承 `voice_typing.engine.base.BaseEngine`，实现 5 个抽象方法
- **修改 UI 样式**：编辑 `voice_typing/ui/styles.py` 中的 `DARK_STYLE` / `OVERLAY_STYLE`
- **调试录音**：在 `Recorder.start()` 中添加 `wave` 模块保存音频文件
- **集成热词表**：在 `AlibabaEngine.initialize()` 中调用 `sync_vocabulary()`
- **单元测试**：在 `tests/` 目录下添加测试用例

---

## 已知问题

- [ ] Wayland 环境下全局快捷键可能失效（pynput 依赖 X11）
- [ ] faster-whisper 首次加载模型较慢（~5-10 秒）
- [ ] 长时间录音（>60 秒）可能导致内存占用过高
- [ ] 热词表功能未集成到主流程

---

## 版本历史

- **v1.3.4**（2026-05-20）：当前版本，重构为标准 Python 包结构
- **v1.0.0**（2026-05-18）：首个 deb 发布版本

---

## 相关链接

- GitHub 仓库：https://github.com/hongyan199048/voice_typing
- 阿里云 DashScope：https://dashscope.console.aliyun.com/
- faster-whisper：https://github.com/SYSTRAN/faster-whisper
