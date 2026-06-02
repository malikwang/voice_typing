#!/usr/bin/env python3
"""VoiceType — 实时语音转文字桌面应用"""

import os
import signal
import sys
import subprocess
import threading
from functools import partial

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, Qt, QTimer
from PyQt5.QtWidgets import QApplication

from voice_typing.core.config import load_config
from voice_typing.core.hotkey import HotkeyManager
from voice_typing.engine.mimo import MimoEngine
from voice_typing.ui.styles import DARK_STYLE, OVERLAY_STYLE
from voice_typing.ui.settings import SettingsWindow
from voice_typing.ui.overlay import OverlayWindow
from voice_typing.recorder import Recorder


class VoiceTypingApp(QObject):
    """主应用控制器"""

    recording_start_signal = pyqtSignal()
    recording_stop_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._config = load_config()
        self._engine = None
        self._recorder = None

        self._create_engine()

        self.recording_start_signal.connect(self._on_recording_start_main_thread)
        self.recording_stop_signal.connect(self._on_recording_stop_main_thread)

        self._hotkey = HotkeyManager(self._config.get("hotkey", ["ctrl", "alt", "v"]))
        self._hotkey.set_callbacks(
            on_start=self._on_recording_start_callback,
            on_stop=self._on_recording_stop_callback,
        )
        self._hotkey.start()

        self._settings = SettingsWindow(self._config, self._hotkey)
        self._settings.engine_changed.connect(self._on_engine_changed)
        self._overlay = OverlayWindow()
        self._overlay.show()

    def _create_engine(self):
        self._engine = MimoEngine(
            api_key=self._config.get("mimo_api_key", ""),
        )
        self._engine.initialize()

    def _on_engine_changed(self, engine):
        self._engine = engine

    def _on_recording_start_callback(self):
        print("[DEBUG] _on_recording_start_callback 被调用（后台线程）")
        self.recording_start_signal.emit()

    def _on_recording_stop_callback(self):
        print("[DEBUG] _on_recording_stop_callback 被调用（后台线程）")
        self.recording_stop_signal.emit()

    @pyqtSlot()
    def _on_recording_start_main_thread(self):
        print("[DEBUG] _on_recording_start_main_thread 被调用（主线程）")
        self._overlay.start_recording()
        self._recorder = Recorder(self._engine, app_obj=self)
        print(f"[DEBUG] Recorder 创建完成: {self._recorder}")
        print(f"[DEBUG] 连接 text_update 信号...")
        self._recorder.text_update.connect(self._overlay.update_text)
        print(f"[DEBUG] 启动录音...")
        self._recorder.start()
        print("[DEBUG] 录音已启动")

    @pyqtSlot()
    def _on_recording_stop_main_thread(self):
        if self._recorder:
            self._recorder.stop()

    @pyqtSlot(str)
    def _on_recording_done(self, text):
        print(f"[DEBUG] _on_recording_done 被调用，文本: '{text}'")
        self._hotkey._recording = False
        self._overlay.stop_recording()
        if text:
            print(f"[识别结果] {text}")
            self._overlay.set_text(text)
            QTimer.singleShot(300, lambda: self._type_text(text))
            QTimer.singleShot(2500, self._overlay.reset)
        else:
            print("[DEBUG] 文本为空，不执行粘贴")
            self._overlay.reset()


    _TERMINAL_CLASSES = [
        "gnome-terminal", "kitty", "alacritty", "xfce4-terminal",
        "tilix", "konsole", "terminator", "xterm", "urxvt", "rxvt",
        "qterminal", "lxterminal", "mate-terminal", "deepin-terminal",
        "io.elementary.terminal", "wezterm", "st-", "tilda", "guake",
    ]

    @classmethod
    def _is_terminal_window(cls):
        try:
            wid = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True, text=True, timeout=1,
            ).stdout.strip()
            if not wid:
                return False
            result = subprocess.run(
                ["xprop", "-id", wid, "WM_CLASS"],
                capture_output=True, text=True, timeout=1,
            )
            # WM_CLASS 输出格式: WM_CLASS(STRING) = "gnome-terminal-server", "Gnome-terminal"
            wm_class = result.stdout.strip().lower()
            is_terminal = any(t in wm_class for t in cls._TERMINAL_CLASSES)
            print(f"[DEBUG] WM_CLASS: {wm_class}, 是终端: {is_terminal}")
            return is_terminal
        except FileNotFoundError:
            print("[ERROR] xdotool 或 xprop 未安装")
            return False
        except Exception as e:
            print(f"[DEBUG] _is_terminal_window 异常: {e}")
            return False

    def _type_text(self, text):
        print(f"[识别结果] {text}")
        if not text:
            return

        try:
            # 写入剪贴板
            proc = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            proc.communicate(input=text.encode("utf-8"), timeout=1)
            if proc.returncode != 0:
                print(f"[ERROR] xclip 写入失败，返回码: {proc.returncode}")
                return

            # 暂停热键触发（不停止 listener，避免 X11 焦点丢失）
            self._hotkey.pause()

            # 清除 X11 层面卡住的修饰键，防止光标消失 / 快捷键失效
            self._hotkey.clear_x11_modifiers()

            if self._is_terminal_window():
                subprocess.run(
                    ["xdotool", "key", "ctrl+shift+v"],
                    timeout=2,
                )
            else:
                subprocess.run(
                    ["xdotool", "key", "ctrl+v"],
                    timeout=2,
                )

            self._hotkey.resume()
        except Exception as e:
            print(f"[ERROR] 粘贴过程出错: {e}")
            try:
                self._hotkey.resume()
            except Exception:
                pass

    def run(self):
        print("[DEBUG] 显示设置窗口...")
        self._settings.show()
        print("[DEBUG] 窗口已调用 show()")
        print(f"[DEBUG] 窗口可见性: {self._settings.isVisible()}")
        print(f"[DEBUG] 窗口大小: {self._settings.size()}")
        sys.exit(QApplication.instance().exec())


def main():
    print("[DEBUG] 启动应用...")
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(DARK_STYLE + OVERLAY_STYLE)
    # 定时器让 Python 有机会处理信号（如 Ctrl+C）
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(200)
    print("[DEBUG] QApplication 已创建")
    voice_app = VoiceTypingApp()
    print("[DEBUG] VoiceTypingApp 已初始化")
    voice_app.run()


if __name__ == "__main__":
    main()
