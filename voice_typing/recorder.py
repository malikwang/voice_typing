"""录音 + ASR 控制器"""

import queue
import threading
import time

import pyaudio
from PyQt5.QtCore import pyqtSignal, QObject, Qt, QMetaObject, Q_ARG

from voice_typing.core.config import load_config

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
        self._app_obj = app_obj
        self._last_text = ""
        self._last_text_time = 0
        self._silence_timeout = load_config().get("silence_timeout", 3.0)

    def start(self):
        self._p = pyaudio.PyAudio()
        self._recording = True
        self._audio_queue = queue.Queue()
        self._last_text = ""
        self._last_text_time = time.time()

        if not self._engine.is_available():
            self._engine.initialize()

        self._engine.start()
        if hasattr(self._engine, "set_text_callback"):
            self._engine.set_text_callback(self._on_text_update)

        threading.Thread(target=self._record_audio, daemon=True).start()
        threading.Thread(target=self._feed_engine, daemon=True).start()
        threading.Thread(target=self._silence_watchdog, daemon=True).start()

    def stop(self):
        self._recording = False

    def _on_text_update(self, text):
        if text != self._last_text:
            self._last_text = text
            self._last_text_time = time.time()
        self.text_update.emit(text)

    def _silence_watchdog(self):
        """监控静默：有文本产出后，连续 N 秒无新内容则自动停止"""
        if not self._silence_timeout or self._silence_timeout <= 0:
            return
        while self._recording:
            time.sleep(0.5)
            if not self._recording:
                return
            if self._last_text and time.time() - self._last_text_time >= self._silence_timeout:
                print(f"[AUTO-STOP] 静默 {self._silence_timeout}s，自动停止录音")
                self._recording = False
                return

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
        while self._recording or (self._audio_queue and not self._audio_queue.empty()):
            try:
                data = self._audio_queue.get(timeout=0.3)
                self._engine.send_audio(data)
            except queue.Empty:
                continue

        print("[DEBUG] 录音结束，调用 engine.stop()...")
        final_text = self._engine.stop()
        print(f"[DEBUG] engine.stop() 返回文本: '{final_text}'")

        if self._app_obj:
            QMetaObject.invokeMethod(
                self._app_obj,
                "_on_recording_done",
                Qt.QueuedConnection,
                Q_ARG(str, final_text)
            )
