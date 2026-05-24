"""录音 + ASR 控制器"""

import queue
import threading

import pyaudio
from PyQt5.QtCore import pyqtSignal, QObject, Qt, QMetaObject, Q_ARG

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
