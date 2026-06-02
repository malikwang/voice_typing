"""录音 + ASR 控制器"""

import queue
import struct
import subprocess
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
    def start(self):
        self._p = pyaudio.PyAudio()
        self._recording = True
        self._audio_queue = queue.Queue()
        self._last_text = ""
        self._last_text_time = time.time()

        # 先启动录音，避免丢失开头音频
        threading.Thread(target=self._record_audio, daemon=True).start()

        if not self._engine.is_available():
            self._engine.initialize()

        self._engine.start()
        if hasattr(self._engine, "set_text_callback"):
            self._engine.set_text_callback(self._on_text_update)

        threading.Thread(target=self._feed_engine, daemon=True).start()

    def stop(self):
        self._recording = False

    def _on_text_update(self, text):
        self.text_update.emit(text)

    def _record_audio(self):
        # 设置麦克风增益为 35%，防止削波导致 ASR 无法识别
        try:
            subprocess.run(["pactl", "set-source-volume", "@DEFAULT_SOURCE@", "35%"],
                          timeout=2, capture_output=True)
            result = subprocess.run(["pactl", "get-source-volume", "@DEFAULT_SOURCE@"],
                                    timeout=2, capture_output=True, text=True)
            print(f"[录音] 麦克风增益: {result.stdout.strip()}", flush=True)
        except Exception as e:
            print(f"[录音] 设置增益失败: {e}", flush=True)

        try:
            stream = self._p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
            )
            print(f"[录音] 麦克风流已打开", flush=True)
        except Exception as e:
            print(f"[录音] 麦克风打开失败: {e}", flush=True)
            self.recording_done.emit("")
            return

        chunk_count = 0
        while self._recording:
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                self._audio_queue.put(data)
                chunk_count += 1
                if chunk_count == 1:
                    print(f"[录音] 第一个音频块已入队", flush=True)
                # 每秒打印一次 RMS 音量（前 5 秒）
                if chunk_count <= 25 and chunk_count % 5 == 1:
                    samples = struct.unpack(f'<{len(data)//2}h', data)
                    rms = int((sum(s*s for s in samples) / len(samples)) ** 0.5)
                    print(f"[录音] chunk={chunk_count} RMS={rms}", flush=True)
            except Exception as e:
                print(f"[录音] 读取异常: {e}", flush=True)
                break

        print(f"[录音] 录音结束，共 {chunk_count} 块", flush=True)
        stream.stop_stream()
        stream.close()
        self._p.terminate()

    def _feed_engine(self):
        fed_count = 0
        while self._recording or (self._audio_queue and not self._audio_queue.empty()):
            try:
                data = self._audio_queue.get(timeout=0.3)
                self._engine.send_audio(data)
                fed_count += 1
                if fed_count == 1:
                    print(f"[Feed] 第一个音频块已送入引擎", flush=True)
            except queue.Empty:
                continue

        print(f"[Feed] 共送入 {fed_count} 块，调用 engine.stop()...", flush=True)
        final_text = self._engine.stop()
        print(f"[DEBUG] engine.stop() 返回文本: '{final_text}'", flush=True)

        if self._app_obj:
            QMetaObject.invokeMethod(
                self._app_obj,
                "_on_recording_done",
                Qt.QueuedConnection,
                Q_ARG(str, final_text)
            )
