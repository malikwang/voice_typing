"""阿里云 Paraformer 实时语音识别引擎"""

import queue
import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback

from engine.base_engine import BaseEngine


class ParaformerCallback(RecognitionCallback):
    """接收实时识别结果"""

    def __init__(self):
        super().__init__()
        self.final_text = ""
        self._on_text = None

    def set_on_text(self, callback):
        self._on_text = callback

    def on_event(self, result):
        sentence = result.get_sentence()
        if sentence and sentence.get("text"):
            self.final_text = sentence["text"]
            if self._on_text:
                self._on_text(self.final_text)


class AlibabaEngine(BaseEngine):
    """阿里云 Paraformer 实时语音识别"""

    name = "阿里云 Paraformer"

    def __init__(self, api_key: str = ""):
        self._api_key = api_key
        self._recognition = None
        self._callback = None
        self._queue = queue.Queue()
        self._running = False

    def initialize(self) -> bool:
        if not self._api_key:
            return False
        dashscope.api_key = self._api_key
        return True

    def is_available(self) -> bool:
        return bool(self._api_key)

    def set_api_key(self, key: str):
        self._api_key = key

    def start(self):
        self._callback = ParaformerCallback()
        self._queue = queue.Queue()
        self._running = True

        self._recognition = Recognition(
            model="paraformer-realtime-v2",
            format="pcm",
            sample_rate=16000,
            callback=self._callback,
        )
        self._recognition.start()

    def set_text_callback(self, cb):
        if self._callback:
            self._callback.set_on_text(cb)

    def send_audio(self, pcm_bytes: bytes):
        if self._running and self._recognition:
            self._recognition.send_audio_frame(pcm_bytes)

    def stop(self) -> str:
        self._running = False
        if self._recognition:
            self._recognition.stop()
        return self._callback.final_text.strip() if self._callback else ""
