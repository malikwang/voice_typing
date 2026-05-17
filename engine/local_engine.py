"""faster-whisper 本地语音识别引擎"""

import os
import queue
import threading
import tempfile
import wave

import numpy as np
from engine.base_engine import BaseEngine

WHISPER_MODELS = {
    "tiny": "tiny",
    "base": "base",
    "small": "small",
    "medium": "medium",
}

MODEL_DIR = os.path.expanduser("~/.cache/voice_typing/models")


class LocalEngine(BaseEngine):
    """faster-whisper 本地离线引擎"""

    name = "本地 faster-whisper"

    def __init__(self, model_size: str = "base"):
        self._model_size = model_size
        self._model = None
        self._running = False
        self._audio_buffer = []
        self._text_callback = None

    def initialize(self) -> bool:
        try:
            from faster_whisper import WhisperModel

            model_name = WHISPER_MODELS.get(self._model_size, "base")
            os.makedirs(MODEL_DIR, exist_ok=True)

            self._model = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",
                download_root=MODEL_DIR,
            )
            return True
        except Exception as e:
            print(f"[LocalEngine] 初始化失败: {e}")
            return False

    def is_available(self) -> bool:
        if self._model is not None:
            return True
        # 检查模型文件是否存在
        model_name = WHISPER_MODELS.get(self._model_size, "base")
        model_path = os.path.join(MODEL_DIR, f"models--Systran--faster-whisper-{model_name}")
        return os.path.exists(model_path)

    def set_text_callback(self, cb):
        self._text_callback = cb

    def start(self):
        self._running = True
        self._audio_buffer = []

    def send_audio(self, pcm_bytes: bytes):
        if self._running:
            self._audio_buffer.append(pcm_bytes)

    def stop(self) -> str:
        self._running = False
        if not self._audio_buffer or self._model is None:
            return ""

        # 将 PCM 数据写入临时 WAV 文件
        audio_data = b"".join(self._audio_buffer)
        tmp_path = os.path.join(tempfile.gettempdir(), "voice_typing_tmp.wav")

        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(16000)
            wf.writeframes(audio_data)

        # 转写
        try:
            segments, _ = self._model.transcribe(
                tmp_path,
                language="zh",
                beam_size=5,
                vad_filter=True,
            )
            text = " ".join(seg.text.strip() for seg in segments)
            if self._text_callback:
                self._text_callback(text)
            return text
        except Exception as e:
            print(f"[LocalEngine] 转写失败: {e}")
            return ""
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


def download_model(model_size: str, progress_callback=None):
    """下载 faster-whisper 模型文件，通过 progress_callback 报告进度"""
    os.makedirs(MODEL_DIR, exist_ok=True)
    model_name = WHISPER_MODELS.get(model_size, "base")

    try:
        from huggingface_hub import snapshot_download
        import time

        repo_id = f"Systran/faster-whisper-{model_name}"
        local_dir = os.path.join(MODEL_DIR, f"models--Systran--faster-whisper-{model_name}")

        # 模型大小估算（MB）
        model_sizes = {"tiny": 75, "base": 145, "small": 488, "medium": 1500}
        expected_mb = model_sizes.get(model_size, 145)

        if progress_callback:
            progress_callback(0, "连接服务器...")

        # 启动下载线程
        download_done = threading.Event()
        download_error = None

        def do_download():
            nonlocal download_error
            try:
                snapshot_download(
                    repo_id,
                    local_dir=local_dir,
                    local_dir_use_symlinks=False,
                )
            except Exception as e:
                download_error = e
            finally:
                download_done.set()

        dl_thread = threading.Thread(target=do_download, daemon=True)
        dl_thread.start()

        # 监控下载进度（通过目录大小）
        last_percent = 0
        while not download_done.is_set():
            if os.path.exists(local_dir):
                size_mb = sum(
                    os.path.getsize(os.path.join(dp, f))
                    for dp, dn, filenames in os.walk(local_dir)
                    for f in filenames
                ) / (1024 * 1024)
                percent = min(95, int(100 * size_mb / expected_mb))
                if percent > last_percent and progress_callback:
                    last_percent = percent
                    progress_callback(percent, f"{percent}% ({int(size_mb)}MB)")
            time.sleep(0.5)

        if download_error:
            raise download_error

        if progress_callback:
            progress_callback(100, "完成")
        return True

    except ImportError:
        # 没有 huggingface_hub，用 faster_whisper 自带的
        from faster_whisper.utils import download_model as _download
        if progress_callback:
            progress_callback(50, "下载中（无进度详情）")
        _download(model_name, local_files_only=False, cache_dir=MODEL_DIR)
        if progress_callback:
            progress_callback(100, "完成")
        return True
    except Exception as e:
        print(f"[下载失败] {e}")
        if progress_callback:
            progress_callback(0, f"失败: {str(e)[:30]}")
        return False
