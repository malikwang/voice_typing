#!/usr/bin/env python3
"""VoiceType — 实时语音转文字桌面应用"""

import os
import sys
import queue
import threading
import subprocess
from functools import partial

import pyaudio
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, Qt, QTimer, QMetaObject, Q_ARG
from PyQt5.QtWidgets import QApplication

from config_manager import load_config
from hotkey_manager import HotkeyManager
from engine.alibaba_engine import AlibabaEngine
from engine.local_engine import LocalEngine
from ui.styles import DARK_STYLE, OVERLAY_STYLE
from ui.settings_window import SettingsWindow
from ui.overlay_window import OverlayWindow

SAMPLE_RATE = 16000
CHUNK_SIZE = 3200  # 200ms


class Recorder(QObject):
    """录音 + ASR 控制器，在主线程中用信号通信"""

    text_update = pyqtSignal(str)
    recording_done = pyqtSignal(str)

    def __init__(self, engine, app_obj=None):
        super().__init__()
        self._engine = engine
        self._recording = False
        self._audio_queue = None
        self._p = None
        self._app_obj = app_obj  # VoiceTypingApp 对象引用

    def start(self):
        self._p = pyaudio.PyAudio()
        self._recording = True
        self._audio_queue = queue.Queue()

        # 初始化引擎
        if not self._engine.is_available():
            self._engine.initialize()

        self._engine.start()
        if hasattr(self._engine, "set_text_callback"):
            self._engine.set_text_callback(lambda t: self.text_update.emit(t))

        # 录音线程
        threading.Thread(target=self._record_audio, daemon=True).start()
        # 音频推流线程
        threading.Thread(target=self._feed_engine, daemon=True).start()

    def stop(self):
        self._recording = False

    def _record_audio(self):
        try:
            stream = self._p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
            )
        except Exception:
            self.recording_done.emit("")
            return

        while self._recording:
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                self._audio_queue.put(data)
            except Exception:
                break

        stream.stop_stream()
        stream.close()
        self._p.terminate()

    def _feed_engine(self):
        try:
            self._engine.set_text_callback(lambda t: self.text_update.emit(t))
        except Exception:
            pass

        while self._recording or (self._audio_queue and not self._audio_queue.empty()):
            try:
                data = self._audio_queue.get(timeout=0.3)
                self._engine.send_audio(data)
            except queue.Empty:
                continue

        print("[DEBUG] 录音结束，调用 engine.stop()...")
        final_text = self._engine.stop()
        print(f"[DEBUG] engine.stop() 返回文本: '{final_text}'")

        # 使用 QMetaObject.invokeMethod 在主线程中调用
        if self._app_obj:
            print("[DEBUG] 使用 QMetaObject.invokeMethod 调用 _on_recording_done...")
            QMetaObject.invokeMethod(
                self._app_obj,
                "_on_recording_done",
                Qt.QueuedConnection,
                Q_ARG(str, final_text)
            )
        else:
            print("[DEBUG] 没有设置 app_obj")


class VoiceTypingApp(QObject):
    """主应用控制器"""

    # 定义信号，用于从后台线程安全地触发主线程操作
    recording_start_signal = pyqtSignal()
    recording_stop_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._config = load_config()
        self._engine = None
        self._recorder = None

        # 创建引擎
        self._create_engine()

        # 连接信号到槽
        self.recording_start_signal.connect(self._on_recording_start_main_thread)
        self.recording_stop_signal.connect(self._on_recording_stop_main_thread)

        # 快捷键
        self._hotkey = HotkeyManager(self._config.get("hotkey", ["ctrl", "alt", "v"]))
        self._hotkey.set_callbacks(
            on_start=self._on_recording_start_callback,
            on_stop=self._on_recording_stop_callback,
        )
        self._hotkey.start()

        # UI
        self._settings = SettingsWindow(self._config, self._hotkey)
        self._settings.engine_changed.connect(self._on_engine_changed)
        self._overlay = OverlayWindow()
        self._overlay.show()  # 启动时就显示浮窗

    def _create_engine(self):
        engine_type = self._config["engine"]
        if engine_type == "alibaba":
            self._engine = AlibabaEngine(api_key=self._config.get("alibaba_api_key", ""))
        else:
            self._engine = LocalEngine(model_size=self._config.get("local_model", "base"))
        self._engine.initialize()

    def _on_engine_changed(self, engine):
        """设置窗口切换引擎时回调"""
        self._engine = engine

    def _on_recording_start_callback(self):
        """快捷键回调（后台线程），发送信号到主线程"""
        print("[DEBUG] _on_recording_start_callback 被调用（后台线程）")
        self.recording_start_signal.emit()

    def _on_recording_stop_callback(self):
        """快捷键回调（后台线程），发送信号到主线程"""
        print("[DEBUG] _on_recording_stop_callback 被调用（后台线程）")
        self.recording_stop_signal.emit()

    @pyqtSlot()
    def _on_recording_start_main_thread(self):
        """在主线程中处理录音开始"""
        print("[DEBUG] _on_recording_start_main_thread 被调用（主线程）")
        self._overlay.start_recording()  # 开始录音动画
        self._recorder = Recorder(self._engine, app_obj=self)
        print(f"[DEBUG] Recorder 创建完成: {self._recorder}")
        print(f"[DEBUG] 连接 text_update 信号...")
        self._recorder.text_update.connect(self._overlay.set_text)
        print(f"[DEBUG] 启动录音...")
        self._recorder.start()
        print("[DEBUG] 录音已启动")

    @pyqtSlot()
    def _on_recording_stop_main_thread(self):
        """在主线程中处理录音停止"""
        if self._recorder:
            self._recorder.stop()

    @pyqtSlot(str)
    def _on_recording_done(self, text):
        print(f"[DEBUG] _on_recording_done 被调用，文本: '{text}'")
        self._overlay.stop_recording()  # 停止录音动画
        if text:
            print("[DEBUG] 文本非空，调用 _type_text")
            self._type_text(text)
            # 粘贴完成后延迟恢复最小状态
            QTimer.singleShot(2000, self._overlay.reset)
        else:
            print("[DEBUG] 文本为空，不执行粘贴")
            self._overlay.reset()

    @staticmethod
    def _type_text(text):
        print(f"[识别结果] {text}")
        if not text:
            print("[DEBUG] 文本为空，跳过粘贴")
            return

        try:
            # 写入剪贴板 - 使用 Popen 异步方式
            print("[DEBUG] 写入剪贴板...")
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
            print("[DEBUG] 剪贴板写入成功")

            # 等待剪贴板写入完成
            import time
            time.sleep(0.3)

            # 模拟 Ctrl+V 粘贴
            print("[DEBUG] 执行粘贴...")
            subprocess.run(
                ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1
            )
            print("[DEBUG] 粘贴命令执行完成")
        except subprocess.TimeoutExpired as e:
            print(f"[ERROR] 命令超时: {e}")
        except Exception as e:
            print(f"[ERROR] 粘贴过程出错: {e}")

    def run(self):
        print("[DEBUG] 显示设置窗口...")
        self._settings.show()
        print("[DEBUG] 窗口已调用 show()")
        print(f"[DEBUG] 窗口可见性: {self._settings.isVisible()}")
        print(f"[DEBUG] 窗口大小: {self._settings.size()}")
        sys.exit(QApplication.instance().exec())


def main():
    print("[DEBUG] 启动应用...")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(DARK_STYLE + OVERLAY_STYLE)
    print("[DEBUG] QApplication 已创建")
    voice_app = VoiceTypingApp()
    print("[DEBUG] VoiceTypingApp 已初始化")
    voice_app.run()


if __name__ == "__main__":
    main()
