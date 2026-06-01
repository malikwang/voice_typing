"""全局快捷键管理 — 基于 pynput 的 toggle 模式监听（按一次开始，再按一次停止）"""

import subprocess
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
    """全局 toggle 快捷键管理

    按一次快捷键开始录音，再按一次停止录音。

    关键设计：
    - pause/resume 不停止 pynput listener（避免 X11 grab 释放导致窗口焦点丢失），
      仅设置 _paused 标志屏蔽热键触发
    - 卡键检测线程：超过 MAX_KEY_HOLD_SEC 未释放的按键自动清除，
      防止 X11 丢失 key-up 事件导致修饰键永久残留
    """

    MAX_KEY_HOLD_SEC = 10.0        # 单键最长保持，超时自动清除
    STALE_CHECK_INTERVAL = 3.0     # 卡键检测间隔
    DEBOUNCE_SEC = 0.3             # 防抖：两次 toggle 之间的最小间隔

    def __init__(self, hotkey_list=None):
        self._keys = set()
        self._press_times = {}      # key → timestamp，检测卡键
        self._lock = threading.RLock()
        self._listener = None
        self._recording = False
        self._on_start = None
        self._on_stop = None
        self._hotkey_set = frozenset()
        self._is_single_key = False
        self._paused = False
        self._stale_timer_running = False
        self._last_toggle_time = 0  # 防抖时间戳

        if hotkey_list:
            self.set_hotkey(hotkey_list)

    # ---- public API ----

    def set_hotkey(self, hotkey_list):
        keys = frozenset(_str_to_key(s) for s in hotkey_list)
        self._hotkey_set = keys
        self._is_single_key = len(hotkey_list) == 1
        self._clear_state()

    def set_callbacks(self, on_start, on_stop):
        self._on_start = on_start
        self._on_stop = on_stop

    def start(self):
        if self._listener is not None:
            return
        self._clear_state()
        self._paused = False
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=False,
        )
        self._listener.start()
        self._start_stale_checker()

    def stop(self):
        self._stop_stale_checker()
        if self._listener:
            self._listener.stop()
            self._listener = None
        self._clear_state()

    def pause(self):
        """暂停热键触发（粘贴前调用），不停止监听器避免 X11 焦点丢失"""
        with self._lock:
            self._paused = True
            self._keys.clear()
            self._press_times.clear()
            self._recording = False

    def resume(self):
        """恢复热键触发（粘贴后调用）"""
        with self._lock:
            self._paused = False
            self._keys.clear()
            self._press_times.clear()

    @staticmethod
    def clear_x11_modifiers():
        """释放 X11 层面所有卡住的修饰键（解决丢事件导致的系统级卡键）"""
        try:
            subprocess.run(
                ["xdotool", "keyup", "ctrl", "alt", "shift", "super"],
                timeout=1,
                capture_output=True,
            )
        except Exception:
            pass

    # ---- 内部 ----

    def _clear_state(self):
        with self._lock:
            self._keys.clear()
            self._press_times.clear()
            self._recording = False
            self._last_toggle_time = 0

    def _start_stale_checker(self):
        self._stop_stale_checker()
        self._stale_timer_running = True
        threading.Thread(target=self._stale_check_loop, daemon=True).start()

    def _stop_stale_checker(self):
        self._stale_timer_running = False

    def _stale_check_loop(self):
        while self._stale_timer_running:
            time.sleep(self.STALE_CHECK_INTERVAL)
            if not self._stale_timer_running:
                return
            self._purge_stale_keys()

    def _purge_stale_keys(self):
        now = time.time()
        with self._lock:
            stale = [
                k for k, t in self._press_times.items()
                if now - t > self.MAX_KEY_HOLD_SEC
            ]
            if stale:
                for k in stale:
                    self._keys.discard(k)
                    self._press_times.pop(k, None)
                self.clear_x11_modifiers()

    # ---- toggle 逻辑 ----

    def _toggle(self):
        """切换录音状态：未录音→开始，录音中→停止"""
        now = time.time()
        if now - self._last_toggle_time < self.DEBOUNCE_SEC:
            return
        self._last_toggle_time = now

        if not self._recording:
            self._recording = True
            if self._on_start:
                self._on_start()
        else:
            self._recording = False
            if self._on_stop:
                self._on_stop()

    # ---- 事件分发 ----

    def _on_press(self, key):
        with self._lock:
            k = _norm(key)
            if k in self._keys:
                return
            self._keys.add(k)
            self._press_times[k] = time.time()

            if not self._hotkey_set or self._paused:
                return

            if self._is_single_key:
                if k in self._hotkey_set:
                    self._toggle()
            else:
                if self._hotkey_set.issubset(self._keys):
                    self._toggle()

    def _on_release(self, key):
        with self._lock:
            k = _norm(key)
            self._keys.discard(k)
            self._press_times.pop(k, None)

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
