"""全局快捷键管理 — 基于 pynput 的 push-to-talk 监听"""

import threading
import pynput.keyboard as keyboard


def _norm(key):
    """将左右修饰键归一化为通用形式"""
    if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
        return keyboard.Key.ctrl
    if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
        return keyboard.Key.alt
    if key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
        return keyboard.Key.shift
    return key


def _key_to_str(key):
    """将 pynput Key 转为配置中的字符串"""
    mapping = {
        keyboard.Key.ctrl: "ctrl",
        keyboard.Key.alt: "alt",
        keyboard.Key.shift: "shift",
        keyboard.Key.cmd: "super",
    }
    if hasattr(key, "char") and key.char:
        return key.char.lower()
    return mapping.get(key, "")


def _str_to_key(s):
    """将配置字符串转为 pynput Key"""
    mapping = {
        "ctrl": keyboard.Key.ctrl,
        "alt": keyboard.Key.alt,
        "shift": keyboard.Key.shift,
        "super": keyboard.Key.cmd,
    }
    if s in mapping:
        return mapping[s]
    return keyboard.KeyCode.from_char(s)


class HotkeyManager:
    """全局 push-to-talk 快捷键管理"""

    def __init__(self, hotkey_list=None):
        """
        hotkey_list: 如 ["ctrl", "alt", "v"]
        """
        self._keys = set()
        self._lock = threading.Lock()
        self._listener = None
        self._recording = False
        self._on_start = None
        self._on_stop = None
        self._hotkey_set = frozenset()

        if hotkey_list:
            self.set_hotkey(hotkey_list)

    def set_hotkey(self, hotkey_list):
        self._hotkey_set = frozenset(_str_to_key(s) for s in hotkey_list)

    def set_callbacks(self, on_start, on_stop):
        """设置回调: on_start() 开始录音, on_stop() 结束录音"""
        self._on_start = on_start
        self._on_stop = on_stop

    def start(self):
        if self._listener is not None:
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _on_press(self, key):
        with self._lock:
            k = _norm(key)
            self._keys.add(k)
            if self._hotkey_set and self._hotkey_set.issubset(self._keys):
                if not self._recording:
                    self._recording = True
                    if self._on_start:
                        self._on_start()

    def _on_release(self, key):
        with self._lock:
            k = _norm(key)
            self._keys.discard(k)
            if self._hotkey_set and not self._hotkey_set.issubset(self._keys):
                if self._recording:
                    self._recording = False
                    if self._on_stop:
                        self._on_stop()

    @staticmethod
    def record_key_sequence(on_done):
        """
        录制一个快捷键组合（用于设置界面）。
        on_done(hotkey_list): 录制完成后回调，传入 ["ctrl", "alt", "v"] 格式
        """
        recorded = set()
        done = threading.Event()

        KEY_ORDER = {keyboard.Key.ctrl: 0, keyboard.Key.alt: 1, keyboard.Key.shift: 2, keyboard.Key.cmd: 3}

        def on_press(key):
            k = _norm(key)
            recorded.add(k)

        def on_release(key):
            # 稍等检查是否还有键按住
            threading.Timer(0.15, _check_done).start()

        def _check_done():
            if done.is_set():
                return
            # 可用 pynput 内部状态判断，简化处理：直接结束
            done.set()
            # 排序：修饰键在前
            sorted_keys = sorted(recorded, key=lambda k: KEY_ORDER.get(k, 99))
            result = [_key_to_str(k) for k in sorted_keys if _key_to_str(k)]
            listener.stop()
            on_done(result)

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        return listener
