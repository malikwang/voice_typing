#!/usr/bin/env python3
"""VoiceType — 实时语音转文字桌面应用"""

import os
import sys
import subprocess
import threading
import time
from functools import partial

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, Qt, QTimer
from PyQt5.QtWidgets import QApplication

from voice_typing.core.config import load_config
from voice_typing.core.hotkey import HotkeyManager
from voice_typing.engine.alibaba import AlibabaEngine
from voice_typing.engine.local import LocalEngine
from voice_typing.ui.styles import DARK_STYLE, OVERLAY_STYLE
from voice_typing.ui.settings import SettingsWindow
from voice_typing.ui.overlay import OverlayWindow
from voice_typing.recorder import Recorder


class VoiceTypingApp(QObject):
    """主应用控制器"""

    recording_start_signal = pyqtSignal()
    recording_stop_signal = pyqtSignal()
    polish_done = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._config = load_config()
        self._engine = None
        self._recorder = None

        self._create_engine()

        self.recording_start_signal.connect(self._on_recording_start_main_thread)
        self.recording_stop_signal.connect(self._on_recording_stop_main_thread)
        self.polish_done.connect(self._on_polish_done)

        self._hotkey = HotkeyManager(self._config.get("hotkey", ["ctrl", "alt", "v"]))
        self._hotkey.set_callbacks(
            on_start=self._on_recording_start_callback,
            on_stop=self._on_recording_stop_callback,
        )
        self._hotkey.start()

        self._settings = SettingsWindow(self._config, self._hotkey)
        self._settings.engine_changed.connect(self._on_engine_changed)
        self._overlay = OverlayWindow()
        self._overlay.show()

    def _create_engine(self):
        engine_type = self._config["engine"]
        if engine_type == "alibaba":
            self._engine = AlibabaEngine(
                api_key=self._config.get("alibaba_api_key", ""),
                phrase_id=self._config.get("phrase_id", ""),
            )
        else:
            self._engine = LocalEngine(model_size=self._config.get("local_model", "base"))
        self._engine.initialize()

    def _on_engine_changed(self, engine):
        self._engine = engine

    def _on_recording_start_callback(self):
        print("[DEBUG] _on_recording_start_callback 被调用（后台线程）")
        self.recording_start_signal.emit()

    def _on_recording_stop_callback(self):
        print("[DEBUG] _on_recording_stop_callback 被调用（后台线程）")
        self.recording_stop_signal.emit()

    @pyqtSlot()
    def _on_recording_start_main_thread(self):
        print("[DEBUG] _on_recording_start_main_thread 被调用（主线程）")
        self._overlay.start_recording()
        self._recorder = Recorder(self._engine, app_obj=self)
        print(f"[DEBUG] Recorder 创建完成: {self._recorder}")
        print(f"[DEBUG] 连接 text_update 信号...")
        self._recorder.text_update.connect(self._overlay.update_text)
        print(f"[DEBUG] 启动录音...")
        self._recorder.start()
        print("[DEBUG] 录音已启动")

    @pyqtSlot()
    def _on_recording_stop_main_thread(self):
        if self._recorder:
            self._recorder.stop()

    @pyqtSlot(str)
    def _on_recording_done(self, text):
        print(f"[DEBUG] _on_recording_done 被调用，文本: '{text}'")
        self._overlay.stop_recording()
        if text:
            print("[DEBUG] 文本非空，显示原始文字并启动润色")
            self._overlay.set_text(text)
            threading.Thread(target=self._run_polish, args=(text,), daemon=True).start()
        else:
            print("[DEBUG] 文本为空，不执行粘贴")
            self._overlay.reset()

    @pyqtSlot(str)
    def _on_polish_done(self, polished_text):
        print("[DEBUG] 润色完成，粘贴最终文字")
        self._overlay.set_text(polished_text)
        QTimer.singleShot(300, lambda: self._type_text(polished_text))
        QTimer.singleShot(2500, self._overlay.reset)

    def _run_polish(self, raw_text):
        polished = self._polish_text(raw_text)
        polished = self._apply_alias_map(polished)
        self.polish_done.emit(polished)

    def _apply_alias_map(self, text):
        """将发音别名替换为正确词汇"""
        vocab = self._config.get("custom_vocabulary", [])
        for item in vocab:
            if isinstance(item, dict):
                alias = item.get("alias", "")
                term = item.get("term", "")
            else:
                # 旧格式：纯字符串，无别名
                continue
            if alias and alias in text:
                text = text.replace(alias, term)
        return text

    _POLISH_PROMPTS = {
        "light": (
            "你是文本校对助手。请对以下语音转文字内容做极少量的处理："
            "1. 仅删除明显的口语语气词（呃、嗯、啊）"
            "2. 仅补充明显缺失的句号，不要改动其他标点"
            "3. 严格保留原文的语序、用词、断句方式，一字不改"
            "直接输出处理后的文字，不加任何解释。"
        ),
        "medium": (
            "你是文本润色助手。请对以下语音转文字内容做最小限度的处理："
            "1. 删除无意义的语气词（呃、嗯、啊、那个、就是说等）"
            "2. 修正明显的标点错误，补充必要的逗号和句号"
            "3. 保留原有语序、用词和表达风格，不要改写句子结构"
            "4. 不要添加或删减实质性内容"
            "直接输出处理后的文字，不加任何解释。"
        ),
        "strong": (
            "你是文本润色助手。请对以下语音转文字内容进行适度整理："
            "1. 删除语气词（呃、嗯、啊、那个、就是说、然后就是等）"
            "2. 修复重复、卡顿和不连贯的表达，让文字通顺"
            "3. 修正标点符号"
            "4. 尽量保持原意和表达风格，只做必要的最小改动"
            "直接输出处理后的文字，不加任何解释。"
        ),
    }

    def _build_vocabulary_hint(self):
        vocab = self._config.get("custom_vocabulary", [])
        if not vocab:
            return ""
        terms = []
        for item in vocab:
            if isinstance(item, dict):
                terms.append(item.get("term", ""))
            else:
                terms.append(str(item))
        if not terms:
            return ""
        term_list = "、".join(terms)
        return (
            "另外，以下专业词汇可能在语音识别中被转写为发音相近的错词，"
            f"请根据上下文将发音相似的词修正为这些正确词汇：{term_list}。"
        )

    def _polish_text(self, raw_text):
        api_key = self._config.get("alibaba_api_key", "")
        if not api_key:
            print("[润色] 未配置 API Key，跳过润色")
            return raw_text

        strength = self._config.get("polish_strength", "medium")
        system_prompt = self._POLISH_PROMPTS.get(strength, self._POLISH_PROMPTS["medium"])
        system_prompt += self._build_vocabulary_hint()

        try:
            from dashscope import Generation
            import dashscope

            dashscope.api_key = api_key
            response = Generation.call(
                model="qwen-plus",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": raw_text},
                ],
                result_format="message",
            )
            if response.status_code == 200:
                polished = response.output.choices[0].message.content.strip()
                print(f"[润色] 原文: '{raw_text}'")
                print(f"[润色] 结果: '{polished}'")
                return polished
            else:
                print(f"[润色] API 失败: {response.code} {response.message}")
                return raw_text
        except Exception as e:
            print(f"[润色] 异常: {e}")
            return raw_text

    _TERMINAL_CLASSES = [
        "gnome-terminal", "kitty", "alacritty", "xfce4-terminal",
        "tilix", "konsole", "terminator", "xterm", "urxvt", "rxvt",
        "qterminal", "lxterminal", "mate-terminal", "deepin-terminal",
        "io.elementary.terminal", "wezterm", "st-", "tilda", "guake",
    ]

    @classmethod
    def _is_terminal_window(cls):
        try:
            wid = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True, text=True, timeout=1,
            ).stdout.strip()
            if not wid:
                return False
            result = subprocess.run(
                ["xprop", "-id", wid, "WM_CLASS"],
                capture_output=True, text=True, timeout=1,
            )
            # WM_CLASS 输出格式: WM_CLASS(STRING) = "gnome-terminal-server", "Gnome-terminal"
            wm_class = result.stdout.strip().lower()
            is_terminal = any(t in wm_class for t in cls._TERMINAL_CLASSES)
            print(f"[DEBUG] WM_CLASS: {wm_class}, 是终端: {is_terminal}")
            return is_terminal
        except FileNotFoundError:
            print("[ERROR] xdotool 或 xprop 未安装")
            return False
        except Exception as e:
            print(f"[DEBUG] _is_terminal_window 异常: {e}")
            return False

    def _type_text(self, text):
        print(f"[识别结果] {text}")
        if not text:
            return

        from pynput.keyboard import Controller as KBController, Key as KBKey

        try:
            proc = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            proc.communicate(input=text.encode("utf-8"), timeout=1)
            if proc.returncode != 0:
                print(f"[ERROR] xclip 写入失败，返回码: {proc.returncode}")
                return
            time.sleep(0.2)

            self._hotkey.pause()
            time.sleep(0.1)
            try:
                kb = KBController()
                if self._is_terminal_window():
                    print("[DEBUG] 终端窗口 → Ctrl+Shift+V")
                    kb.press(KBKey.ctrl)
                    kb.press(KBKey.shift)
                    time.sleep(0.03)
                    kb.press('v')
                    kb.release('v')
                    time.sleep(0.03)
                    kb.release(KBKey.shift)
                    kb.release(KBKey.ctrl)
                else:
                    print("[DEBUG] 非终端窗口 → Ctrl+V")
                    kb.press(KBKey.ctrl)
                    time.sleep(0.03)
                    kb.press('v')
                    kb.release('v')
                    time.sleep(0.03)
                    kb.release(KBKey.ctrl)
            finally:
                time.sleep(0.1)
                self._hotkey.resume()
        except Exception as e:
            print(f"[ERROR] 粘贴过程出错: {e}")

    def run(self):
        print("[DEBUG] 显示设置窗口...")
        self._settings.show()
        print("[DEBUG] 窗口已调用 show()")
        print(f"[DEBUG] 窗口可见性: {self._settings.isVisible()}")
        print(f"[DEBUG] 窗口大小: {self._settings.size()}")
        sys.exit(QApplication.instance().exec())


def main():
    print("[DEBUG] 启动应用...")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(DARK_STYLE + OVERLAY_STYLE)
    print("[DEBUG] QApplication 已创建")
    voice_app = VoiceTypingApp()
    print("[DEBUG] VoiceTypingApp 已初始化")
    voice_app.run()


if __name__ == "__main__":
    main()
