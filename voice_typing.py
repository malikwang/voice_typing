#!/usr/bin/env python3
"""
实时语音转文字 + 自动粘贴工具
按住 Ctrl+Alt+V 说话 → 松开后文字自动粘贴到光标处
后端：阿里云 Paraformer 实时语音识别
"""

import os
import sys
import time
import queue
import threading
import subprocess
import signal

import pyaudio
import dashscope
import pynput.keyboard as keyboard
from dashscope.audio.asr import Recognition, RecognitionCallback

# ---------- 配置 ----------
API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
SAMPLE_RATE = 16000
CHUNK_SIZE = 3200  # 200ms @ 16kHz
# -------------------------


def _norm(key):
    """将左右修饰键归一化为通用形式"""
    if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
        return keyboard.Key.ctrl
    if key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
        return keyboard.Key.alt
    if key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
        return keyboard.Key.shift
    return key


# 归一化后的快捷键组合
HOTKEY = {keyboard.Key.ctrl, keyboard.Key.alt, keyboard.KeyCode.from_char("v")}


class ASRCallback(RecognitionCallback):
    """接收 Paraformer 实时识别结果，并保存最终文本"""

    def __init__(self):
        super().__init__()
        self.final_text = ""
        self._sentences = []  # 累积所有句子 (sentence_id, text)

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
                    sys.stdout.write(f"\r>>> {self.final_text}")
                    sys.stdout.flush()
            else:
                # 实时预览（不保存到 final_text）
                preview = "".join(t for _, t in self._sentences) + text
                sys.stdout.write(f"\r>>> {preview}")
                sys.stdout.flush()


class VoiceTyping:
    def __init__(self):
        if not API_KEY:
            print("[ERROR] 请设置环境变量 DASHSCOPE_API_KEY")
            print("  export DASHSCOPE_API_KEY='your-api-key'")
            sys.exit(1)

        dashscope.api_key = API_KEY
        self._recording = False
        self._audio_queue = None
        self._final_text = ""
        self._p = pyaudio.PyAudio()
        self._current_keys = set()
        self._lock = threading.Lock()

    # ---------- 录音 ----------

    def _record_audio(self):
        stream = self._p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )
        while self._recording:
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                self._audio_queue.put(data)
            except Exception:
                break
        stream.stop_stream()
        stream.close()

    # ---------- ASR ----------

    def _run_asr(self):
        callback = ASRCallback()
        recognition = Recognition(
            model="paraformer-realtime-v2",
            format="pcm",
            sample_rate=SAMPLE_RATE,
            callback=callback,
        )
        recognition.start()

        while self._recording or not self._audio_queue.empty():
            try:
                data = self._audio_queue.get(timeout=0.3)
                recognition.send_audio_frame(data)
            except queue.Empty:
                continue

        recognition.stop()
        return callback.final_text.strip()

    # ---------- 快捷键 ----------

    def _on_press(self, key):
        with self._lock:
            self._current_keys.add(_norm(key))
            if HOTKEY.issubset(self._current_keys) and not self._recording:
                self._start_recording()

    def _on_release(self, key):
        with self._lock:
            self._current_keys.discard(_norm(key))
            if not HOTKEY.issubset(self._current_keys) and self._recording:
                self._stop_recording()

    def _start_recording(self):
        self._recording = True
        self._audio_queue = queue.Queue()
        self._final_text = ""
        threading.Thread(target=self._record_audio, daemon=True).start()
        threading.Thread(target=self._asr_runner, daemon=True).start()
        subprocess.run(["notify-send", "语音输入", "正在聆听...", "-t", "1000"])

    def _stop_recording(self):
        self._recording = False
        # 等待录音和 ASR 线程结束（最多 5 秒）
        deadline = time.monotonic() + 5
        while self._final_text == "" and time.monotonic() < deadline:
            time.sleep(0.05)
        if self._final_text:
            self._type_text(self._final_text)

    def _asr_runner(self):
        self._final_text = self._run_asr()

    # ---------- 文字输出 ----------

    def _type_text(self, text):
        print(f"\n[识别结果] {text}")
        # 写入剪贴板 → 模拟 Ctrl+V
        proc = subprocess.run(
            ["xclip", "-selection", "clipboard", "-in"],
            input=text.encode("utf-8"),
        )
        if proc.returncode != 0:
            print("[ERROR] xclip 写入失败，请安装 xclip: sudo apt install xclip")
            return
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"])

    # ---------- 主入口 ----------

    def run(self):
        print("语音输入工具已启动")
        print("按住 Ctrl+Alt+V 开始录音，松开后自动粘贴\n")

        listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        listener.start()

        signal.signal(signal.SIGINT, lambda s, f: self._cleanup())
        signal.signal(signal.SIGTERM, lambda s, f: self._cleanup())
        try:
            listener.join()
        except KeyboardInterrupt:
            self._cleanup()

    def _cleanup(self):
        self._recording = False
        self._p.terminate()
        print("\n已退出")
        sys.exit(0)


if __name__ == "__main__":
    VoiceTyping().run()
