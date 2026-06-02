"""小米 ASR_Streaming 流式语音识别引擎（WebSocket 二进制协议）"""

import asyncio
import json
import queue
import struct
import threading
import time
import uuid

import websockets

from voice_typing.engine.base import BaseEngine

WS_HOST = "model.mify.ai.srv"
WS_PATH = "/v1/asr"
MODEL = "ASR_Streaming"
PROVIDER_ID = "xiaomi"

CHUNK_SIZE = 4096


def _generate_header(seq_id: int, payload_len: int, request_id_len: int) -> bytes:
    """生成 16 字节协议头"""
    header = bytearray(16)
    header[0] = 0x11  # version=1, type=1
    header[1] = 0x11  # no serialization, no compression
    header[4:8] = struct.pack('>i', seq_id)
    header[8:12] = struct.pack('>i', payload_len)
    header[12:16] = struct.pack('>i', request_id_len)
    return bytes(header)


class MimoEngine(BaseEngine):
    """小米 ASR_Streaming 流式语音识别

    通过 Mify 推理网关的 WebSocket /v1/asr 接口实现实时 ASR。
    使用二进制帧协议，边发音频边收转写结果。
    """

    name = "小米 ASR"

    def __init__(self, api_key: str = ""):
        self._api_key = api_key
        self._running = False
        self._audio_queue = None
        self._text_callback = None
        self._final_text = ""
        self._ws_done = None
        self._t0 = 0

    def _ts(self):
        return f"{time.time() - self._t0:.2f}s"

    def initialize(self) -> bool:
        return bool(self._api_key)

    def is_available(self) -> bool:
        return bool(self._api_key)

    def set_text_callback(self, cb):
        self._text_callback = cb

    def start(self):
        self._running = True
        self._t0 = time.time()
        self._audio_queue = queue.Queue()
        self._final_text = ""
        self._send_finished = False
        self._ws_done = threading.Event()
        self._ws_connected = threading.Event()
        print(f"[MiASR {self._ts()}] start()", flush=True)
        threading.Thread(target=self._run_ws, daemon=True).start()
        # 等待连接就绪再返回，这样录音数据不会积压
        connected = self._ws_connected.wait(timeout=5)
        print(f"[MiASR {self._ts()}] start() 返回, connected={connected}", flush=True)

    def _run_ws(self):
        asyncio.run(self._ws_session())

    async def _ws_session(self):
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "X-Model-Provider-Id": PROVIDER_ID,
            "X-Model-Request-Id": "",
        }
        url = f"ws://{WS_HOST}{WS_PATH}?model={MODEL}"

        try:
            print(f"[MiASR {self._ts()}] 正在连接 {url}", flush=True)
            async with websockets.connect(
                url,
                additional_headers=headers,
                open_timeout=10,
                ping_timeout=20,
                close_timeout=10,
                max_size=10_000_000,
            ) as ws:
                print(f"[MiASR {self._ts()}] 连接成功，队列积压: {self._audio_queue.qsize()}", flush=True)
                self._ws_connected.set()

                request_id = str(uuid.uuid4())
                request_id_bytes = request_id.encode('utf-8')
                request_id_len = len(request_id_bytes)

                send_task = asyncio.create_task(
                    self._send_loop(ws, request_id_bytes, request_id_len)
                )
                recv_task = asyncio.create_task(self._recv_loop(ws))

                await send_task
                try:
                    await asyncio.wait_for(recv_task, timeout=2)
                except asyncio.TimeoutError:
                    print(f"[MiASR {self._ts()}] recv 完成（超时退出）")
                    recv_task.cancel()

        except Exception as e:
            print(f"[MiASR {self._ts()}] WS 异常: {e}")
        finally:
            self._ws_connected.set()
            self._ws_done.set()

    async def _send_loop(self, ws, request_id_bytes: bytes, request_id_len: int):
        """从队列取 PCM 数据，按协议封装发送"""
        loop = asyncio.get_event_loop()
        seq_id = 0
        buffer = bytearray()
        first_send = True

        # 发送 500ms 静音前导缓冲，防止模型丢弃开头音频
        silence = b'\x00' * (16000 * 2 * 500 // 1000)  # 500ms, 16kHz, 16bit
        for i in range(0, len(silence), CHUNK_SIZE):
            chunk = silence[i:i + CHUNK_SIZE]
            seq_id += 1
            header = _generate_header(seq_id, len(chunk), request_id_len)
            await ws.send(header + request_id_bytes + chunk)

        def _drain_queue():
            chunks = []
            while True:
                try:
                    chunks.append(self._audio_queue.get_nowait())
                except queue.Empty:
                    break
            return chunks

        while self._running:
            try:
                data = await loop.run_in_executor(
                    None, lambda: self._audio_queue.get(timeout=0.1)
                )
                buffer.extend(data)
            except queue.Empty:
                continue

            for chunk_data in _drain_queue():
                buffer.extend(chunk_data)

            while len(buffer) >= CHUNK_SIZE:
                chunk = bytes(buffer[:CHUNK_SIZE])
                buffer = buffer[CHUNK_SIZE:]
                seq_id += 1
                header = _generate_header(seq_id, len(chunk), request_id_len)
                await ws.send(header + request_id_bytes + chunk)
                if first_send:
                    print(f"[MiASR {self._ts()}] 首帧已发送", flush=True)
                    first_send = False

        # drain remaining
        for chunk_data in _drain_queue():
            buffer.extend(chunk_data)

        while len(buffer) >= CHUNK_SIZE:
            chunk = bytes(buffer[:CHUNK_SIZE])
            buffer = buffer[CHUNK_SIZE:]
            seq_id += 1
            header = _generate_header(seq_id, len(chunk), request_id_len)
            await ws.send(header + request_id_bytes + chunk)

        # 最后一帧
        seq_id += 1
        chunk = bytes(buffer)
        header = _generate_header(-seq_id, len(chunk), request_id_len)
        await ws.send(header + request_id_bytes + chunk)
        self._send_finished = True
        print(f"[MiASR {self._ts()}] 发送完毕，共 {seq_id} 帧", flush=True)

    async def _recv_loop(self, ws):
        """接收服务端转写结果"""
        try:
            async for msg in ws:
                ts = self._ts()
                text = ""
                if isinstance(msg, str):
                    try:
                        data = json.loads(msg)
                        text = data.get("text", "").strip()
                    except json.JSONDecodeError:
                        text = msg.strip()
                elif isinstance(msg, bytes):
                    try:
                        text = msg.decode('utf-8').strip()
                    except UnicodeDecodeError:
                        pass

                if not text:
                    continue

                self._final_text = text

                if self._send_finished:
                    # 发送完毕后收到的是最终结果，采纳并退出
                    print(f"[MiASR {ts}] 最终: '{text}'", flush=True)
                    if self._text_callback:
                        self._text_callback(text)
                    break
                else:
                    print(f"[MiASR {ts}] 中间: '{text}'", flush=True)
                    if self._text_callback:
                        self._text_callback(text)
        except websockets.exceptions.ConnectionClosed:
            pass

    def send_audio(self, pcm_bytes: bytes):
        if self._running and self._audio_queue is not None:
            self._audio_queue.put(pcm_bytes)

    def stop(self) -> str:
        self._running = False
        # 等待最终结果（发送完毕后服务端返回的最后一条）
        self._ws_done.wait(timeout=10)
        return self._final_text.strip()
