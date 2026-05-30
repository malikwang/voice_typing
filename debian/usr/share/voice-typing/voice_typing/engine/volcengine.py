"""火山引擎 BigModel 流式语音识别引擎"""

import asyncio
import gzip
import json
import queue
import struct
import threading
import uuid

import websockets

from voice_typing.engine.base import BaseEngine

WS_URL = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel"
RESOURCE_ID = "volc.seedasr.sauc.duration"

HDR_CONFIG = bytes([0x11, 0x10, 0x11, 0x00])
HDR_AUDIO = bytes([0x11, 0x20, 0x01, 0x00])
HDR_AUDIO_LAST = bytes([0x11, 0x22, 0x01, 0x00])


def _build_frame(header: bytes, payload: bytes) -> bytes:
    compressed = gzip.compress(payload)
    return header + struct.pack(">I", len(compressed)) + compressed


def _parse_response(msg: bytes):
    """解析二进制响应帧，返回 (text, is_final)"""
    if len(msg) < 8:
        return "", False
    payload_len = struct.unpack(">I", msg[4:8])[0]
    payload = gzip.decompress(msg[8:8 + payload_len])
    data = json.loads(payload)
    if data.get("code") != 20000000:
        return "", False
    results = data.get("result", [])
    if not results:
        return "", False
    text = results[0].get("text", "")
    is_final = results[0].get("definite", False)
    return text, is_final


class VolcengineEngine(BaseEngine):
    """火山引擎流式语音识别（BigModel ASR v2）"""

    name = "火山引擎 BigModel ASR"

    def __init__(self, app_id: str = "", access_token: str = ""):
        self._app_id = app_id
        self._access_token = access_token
        self._running = False
        self._audio_queue = None
        self._text_callback = None
        self._final_text = ""
        self._ws_done = None

    def initialize(self) -> bool:
        return bool(self._app_id and self._access_token)

    def is_available(self) -> bool:
        return bool(self._app_id and self._access_token)

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

    async def _ws_session(self):
        headers = {
            "X-Api-App-Key": self._app_id,
            "X-Api-Access-Key": self._access_token,
            "X-Api-Resource-Id": RESOURCE_ID,
            "X-Api-Request-Id": str(uuid.uuid4()),
            "X-Api-Connect-Id": str(uuid.uuid4()),
        }
        try:
            async with websockets.connect(
                WS_URL,
                additional_headers=headers,
                max_size=10_000_000,
                ping_interval=20,
            ) as ws:
                config = {
                    "user": {"uid": "voice-typing"},
                    "audio": {
                        "format": "pcm", "codec": "raw",
                        "rate": 16000, "bits": 16, "channel": 1,
                    },
                    "request": {
                        "model_name": "bigmodel",
                        "enable_itn": True,
                        "enable_punc": True,
                        "result_type": "single",
                        "language": "zh-CN",
                    },
                }
                payload = json.dumps(config).encode()
                await ws.send(_build_frame(HDR_CONFIG, payload))

                async def send_loop():
                    loop = asyncio.get_event_loop()
                    while self._running:
                        try:
                            data = await loop.run_in_executor(
                                None, lambda: self._audio_queue.get(timeout=0.3)
                            )
                        except queue.Empty:
                            continue
                        await ws.send(_build_frame(HDR_AUDIO, data))
                    # drain remaining audio
                    while True:
                        try:
                            data = self._audio_queue.get_nowait()
                            await ws.send(_build_frame(HDR_AUDIO, data))
                        except queue.Empty:
                            break
                    await ws.send(_build_frame(HDR_AUDIO_LAST, b""))

                async def recv_loop():
                    final_parts = []
                    async for msg in ws:
                        text, is_final = _parse_response(msg)
                        if not text:
                            continue
                        if is_final:
                            # 去重：避免两遍识别返回相同句子
                            if text not in final_parts:
                                final_parts.append(text)
                            self._final_text = "".join(final_parts)
                            preview = self._final_text
                        else:
                            preview = "".join(final_parts) + text
                        if self._text_callback:
                            self._text_callback(preview)

                await asyncio.gather(send_loop(), recv_loop())
        except Exception as e:
            print(f"[Volcengine] WS 连接异常: {e}")
        finally:
            self._ws_done.set()

    def send_audio(self, pcm_bytes: bytes):
        if self._running and self._audio_queue is not None:
            self._audio_queue.put(pcm_bytes)

    def stop(self) -> str:
        self._running = False
        self._ws_done.wait(timeout=10)
        return self._final_text.strip()
