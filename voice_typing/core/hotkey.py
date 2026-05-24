"""全局快捷键管理 — 基于 pynput 的 push-to-talk 监听"""

import threading
import time
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
    if hasattr(key, "name") and key.name:
        return mapping.get(key, key.name)
    if hasattr(key, "vk") and key.vk is not None:
        return f"vk:{key.vk}"
    return ""


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
    if s.startswith("vk:"):
        return keyboard.KeyCode.from_vk(int(s[3:]))
    try:
        return getattr(keyboard.Key, s)
    except AttributeError:
        pass
    return keyboard.KeyCode.from_char(s)


class HotkeyManager:
    """全局 push-to-talk 快捷键管理

    支持两种模式：
    - 组合键（多键）：全部按下立即触发录音
    - 单键长按（一键）：按住超过 1 秒触发录音，松手结束

    录音期间自动 suppress 按键，防止修饰键先松开导致字符键泄漏到应用。
    """

    LONG_PRESS_SEC = 0

    def __init__(self, hotkey_list=None):
        self._keys = set()
        self._lock = threading.RLock()  # 可重入锁，避免 _on_release → _on_long_press_release 死锁
        self._listener = None
        self._recording = False
        self._on_start = None
        self._on_stop = None
        self._hotkey_set = frozenset()
        self._is_long_press = False
        self._press_time = None
        self._long_press_timer = None

        if hotkey_list:
            self.set_hotkey(hotkey_list)

    def set_hotkey(self, hotkey_list):
        keys = frozenset(_str_to_key(s) for s in hotkey_list)
        self._hotkey_set = keys
        self._is_long_press = len(hotkey_list) == 1

    def set_callbacks(self, on_start, on_stop):
        self._on_start = on_start
        self._on_stop = on_stop

    def start(self):
        if self._listener is not None:
            return
        self._start_listener(suppress=False)

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    def pause(self):
        """暂停监听（粘贴前调用，防止 pynput 拦截 XTest 事件）"""
        if self._listener:
            self._listener.stop()
            self._listener = None

    def resume(self):
        """恢复监听（粘贴后调用）"""
        if self._listener is None:
            self._start_listener(suppress=False)

    def _start_listener(self, suppress, on_ready=None):
        """启动键盘监听，suppress=True 时阻塞按键不传递给其他应用。
        在独立线程中切换，避免在 listener 回调中 stop 导致死锁。
        on_ready 在 passthrough 模式 listener 就绪后回调。"""
        def _switch():
            if self._listener:
                self._listener.stop()
            self._listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
                suppress=suppress,
            )
            self._listener.start()
            if on_ready and not suppress:
                on_ready()
        threading.Thread(target=_switch, daemon=True).start()

    # ---- 单键长按模式 ----

    def _on_long_press_start(self):
        with self._lock:
            if self._recording:
                return
            self._recording = True
            self._start_listener(suppress=True)
            if self._on_start:
                self._on_start()

    def _on_long_press_release(self):
        with self._lock:
            if self._long_press_timer:
                self._long_press_timer.cancel()
                self._long_press_timer = None
            self._press_time = None
            if self._recording:
                self._recording = False
                # 等 passthrough listener 就绪后再触发 stop，确保粘贴时按键不被阻塞
                self._start_listener(suppress=False, on_ready=self._on_stop)

    # ---- 组合键模式 ----

    def _check_combo_start(self):
        if self._hotkey_set and self._hotkey_set.issubset(self._keys):
            if not self._recording:
                self._recording = True
                self._start_listener(suppress=True)
                if self._on_start:
                    self._on_start()

    def _check_combo_stop(self):
        if self._hotkey_set and not self._hotkey_set.issubset(self._keys):
            if self._recording:
                self._recording = False
                self._start_listener(suppress=False, on_ready=self._on_stop)

    # ---- 事件分发 ----

    def _on_press(self, key):
        with self._lock:
            k = _norm(key)
            self._keys.add(k)

            if not self._hotkey_set:
                return

            if self._is_long_press:
                if k in self._hotkey_set and self._press_time is None:
                    self._press_time = time.time()
                    if self.LONG_PRESS_SEC <= 0:
                        self._on_long_press_start()
                    else:
                        self._long_press_timer = threading.Timer(
                            self.LONG_PRESS_SEC, self._on_long_press_start
                        )
                        self._long_press_timer.start()
            else:
                self._check_combo_start()

    def _on_release(self, key):
        with self._lock:
            k = _norm(key)
            self._keys.discard(k)

            if not self._hotkey_set:
                return

            if self._is_long_press:
                if k in self._hotkey_set:
                    self._on_long_press_release()
            else:
                self._check_combo_stop()

    @staticmethod
    def record_key_sequence(on_done):
        """录制快捷键组合（用于设置界面）"""
        recorded = set()
        done = threading.Event()

        KEY_ORDER = {
            keyboard.Key.ctrl: 0, keyboard.Key.alt: 1,
            keyboard.Key.shift: 2, keyboard.Key.cmd: 3,
        }

        def on_press(key):
            k = _norm(key)
            recorded.add(k)

        def on_release(key):
            threading.Timer(0.15, _check_done).start()

        def _check_done():
            if done.is_set():
                return
            done.set()
            sorted_keys = sorted(recorded, key=lambda k: KEY_ORDER.get(k, 99))
            result = [_key_to_str(k) for k in sorted_keys if _key_to_str(k)]
            listener.stop()
            on_done(result)

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        return listener
