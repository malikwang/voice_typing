"""阿里云 Paraformer 实时语音识别引擎"""

import queue
import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback

from engine.base_engine import BaseEngine


class ParaformerCallback(RecognitionCallback):
    """接收实时识别结果"""

    def __init__(self, vocabulary=None):
        super().__init__()
        self.final_text = ""
        self._sentences = []  # 累积所有句子
        self._on_text = None
        self._vocabulary = vocabulary or []  # 自定义词库

    def set_on_text(self, callback):
        self._on_text = callback

    def _apply_vocabulary(self, text):
        """应用自定义词库进行后处理（如果 API 不支持热词）"""
        if not self._vocabulary:
            return text
        # 简单替换策略：后续可以优化为模糊匹配
        result = text
        for word in self._vocabulary:
            # 这里可以添加更复杂的匹配逻辑
            pass
        return result

    def on_event(self, result):
        sentence = result.get_sentence()
        if sentence and sentence.get("text"):
            text = sentence["text"]
            sentence_id = sentence.get("sentence_id", 0)
            end_time = sentence.get("end_time")
            is_final = end_time is not None and end_time > 0  # end_time 存在且 > 0 表示句子结束

            # 使用 sentence_id 去重：只在句子最终确定时添加
            if is_final:
                # 检查是否已存在该 sentence_id
                if not any(sid == sentence_id for sid, _ in self._sentences):
                    self._sentences.append((sentence_id, text))
                    self.final_text = "".join(t for _, t in self._sentences)
            else:
                # 实时预览（不保存）
                preview = "".join(t for _, t in self._sentences) + text
                if self._on_text:
                    self._on_text(preview)
                return

            if self._on_text:
                self._on_text(self.final_text)


class AlibabaEngine(BaseEngine):
    """阿里云 Paraformer 实时语音识别"""

    name = "阿里云 Paraformer"

    def __init__(self, api_key: str = "", vocabulary: list = None):
        self._api_key = api_key
        self._recognition = None
        self._callback = None
        self._queue = queue.Queue()
        self._running = False
        self._vocabulary = vocabulary or []

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
        self._callback = ParaformerCallback(vocabulary=self._vocabulary)
        self._queue = queue.Queue()
        self._running = True

        # 尝试使用 vocabulary_id 参数（如果 API 支持）
        recognition_params = {
            "model": "paraformer-realtime-v2",
            "format": "pcm",
            "sample_rate": 16000,
            "callback": self._callback,
            "enable_punctuation_prediction": True,
            "enable_inverse_text_normalization": True,
        }

        # 如果有自定义词库，尝试传递给 API（可能不支持，需要测试）
        # if self._vocabulary:
        #     recognition_params["vocabulary_id"] = self._vocabulary

        self._recognition = Recognition(**recognition_params)
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
