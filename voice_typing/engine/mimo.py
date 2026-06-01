"""小米 MiMo Realtime 流式语音识别引擎"""

import asyncio
import base64
import json
import queue
import threading

import websockets

from voice_typing.engine.base import BaseEngine

WS_URI = "ws://model.mify.ai.srv/v1/realtime?model=mimo-v2-audio-realtime"


class MimoEngine(BaseEngine):
    """小米 MiMo Realtime 流式语音识别

    通过 Mify 推理网关的 WebSocket Realtime API 实现实时 ASR。
    音频格式: PCM 16bit mono，输入 16kHz 会重采样到 24kHz。
    """

    name = "小米 MiMo Realtime"

    def __init__(self, api_key: str = ""):
        self._api_key = api_key
        self._running = False
        self._audio_queue = None
        self._text_callback = None
        self._final_text = ""
        self._ws_done = None

    def initialize(self) -> bool:
        return bool(self._api_key)

    def is_available(self) -> bool:
        return bool(self._api_key)

    def set_text_callback(self, cb):
        self._text_callback = cb

    def start(self):
        self._running = True
        self._audio_queue = queue.Queue()
        self._final_text = ""
        self._ws_done = threading.Event()
        threading.Thread(target=self._run_ws, daemon=True).start()

    def _run_ws(self):
        asyncio.run(self._ws_session())

    def _resample_16k_to_24k(self, pcm_16k: bytes) -> bytes:
        """将 16kHz PCM 重采样到 24kHz (简单线性插值)"""
        import struct
        samples = struct.unpack(f"<{len(pcm_16k)//2}h", pcm_16k)
        n = len(samples)
        ratio = 16000 / 24000
        out_len = int(n / ratio)
        out = []
        for i in range(out_len):
            src_pos = i * ratio
            idx = int(src_pos)
            frac = src_pos - idx
            if idx + 1 < n:
                val = samples[idx] * (1 - frac) + samples[idx + 1] * frac
            else:
                val = samples[idx]
            out.append(int(val))
        return struct.pack(f"<{len(out)}h", *out)

    async def _ws_session(self):
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "X-Model-Provider-Id": "xiaomi",
            "OpenAI-Beta": "realtime=v1",
        }
        try:
            async with websockets.connect(
                WS_URI,
                additional_headers=headers,
                open_timeout=10,
                max_size=10_000_000,
                ping_interval=20,
            ) as ws:
                # 等待 session.created
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if msg.get("type") != "session.created":
                    print(f"[MiMo] 意外事件: {msg.get('type')}")
                    return

                # 配置 session: 关闭 VAD，手动 commit
                await ws.send(json.dumps({
                    "type": "session.update",
                    "session": {
                        "input_audio_transcription": {"model": "whisper-1"},
                        "input_audio_format": "pcm16",
                        "turn_detection": None,
                    },
                }))
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                if msg.get("type") != "session.updated":
                    print(f"[MiMo] session.update 失败: {msg}")
                    return

                async def send_loop():
                    loop = asyncio.get_event_loop()
                    while self._running:
                        try:
                            data = await loop.run_in_executor(
                                None, lambda: self._audio_queue.get(timeout=0.3)
                            )
                        except queue.Empty:
                            continue
                        # 重采样 16kHz → 24kHz
                        data_24k = self._resample_16k_to_24k(data)
                        await ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": base64.b64encode(data_24k).decode(),
                        }))

                    # drain remaining
                    while True:
                        try:
                            data = self._audio_queue.get_nowait()
                            data_24k = self._resample_16k_to_24k(data)
                            await ws.send(json.dumps({
                                "type": "input_audio_buffer.append",
                                "audio": base64.b64encode(data_24k).decode(),
                            }))
                        except queue.Empty:
                            break

                    # commit + 请求转写
                    await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                    await ws.send(json.dumps({"type": "response.create"}))

                async def recv_loop():
                    transcript_parts = []
                    async for msg in ws:
                        data = json.loads(msg)
                        t = data.get("type", "")

                        if t == "conversation.item.input_audio_transcription.delta":
                            delta = data.get("delta", "")
                            # 实时预览
                            preview = "".join(transcript_parts) + delta
                            if self._text_callback:
                                self._text_callback(preview)

                        elif t == "conversation.item.input_audio_transcription.completed":
                            transcript = data.get("transcript", "").strip()
                            if transcript:
                                transcript_parts.append(transcript)
                                self._final_text = "".join(transcript_parts)
                                if self._text_callback:
                                    self._text_callback(self._final_text)

                        elif t == "response.done":
                            break

                        elif t == "error":
                            err = data.get("error", {})
                            print(f"[MiMo] 错误: {err.get('message', '')}")
                            break

                await asyncio.gather(send_loop(), recv_loop())

        except Exception as e:
            print(f"[MiMo] WS 连接异常: {e}")
        finally:
            self._ws_done.set()

    def send_audio(self, pcm_bytes: bytes):
        if self._running and self._audio_queue is not None:
            self._audio_queue.put(pcm_bytes)

    def stop(self) -> str:
        self._running = False
        self._ws_done.wait(timeout=15)
        return self._final_text.strip()
