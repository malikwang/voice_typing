"""设置主窗口"""

import subprocess
import threading

from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QComboBox, QPushButton, QProgressBar,
    QSystemTrayIcon, QMenu, QAction, QApplication, QMessageBox,
)

from config_manager import load_config, save_config
from engine.alibaba_engine import AlibabaEngine
from engine.local_engine import LocalEngine, download_model


def _make_tray_icon():
    """生成绿色圆形托盘图标"""
    pix = QPixmap(32, 32)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor(34, 197, 94)))
    p.setPen(Qt.NoPen)
    p.drawEllipse(4, 4, 24, 24)
    # 白色麦克风简化符号
    p.setBrush(QBrush(QColor(13, 13, 13)))
    p.drawRoundedRect(13, 7, 6, 10, 2, 2)
    p.drawRoundedRect(11, 14, 10, 3, 1, 1)
    p.end()
    return QIcon(pix)


class SettingsWindow(QWidget):
    """VoiceType 设置主窗口"""

    # 信号：引擎变更时通知 main
    engine_changed = pyqtSignal(object)
    # 信号：下载进度更新（从后台线程安全发射）
    download_progress = pyqtSignal(int, str)

    def __init__(self, config, hotkey_manager):
        super().__init__()
        self._config = config
        self._hotkey = hotkey_manager
        self._engine = None
        self._downloading = False

        self._init_ui()
        self._init_tray()
        self._apply_config()
        self._create_engine()

        # 连接下载进度信号
        self.download_progress.connect(self._update_download_progress)

    # ---------- UI 构建 ----------

    def _init_ui(self):
        self.setWindowTitle("VoiceType")
        self.setFixedSize(480, 620)
        self.setWindowIcon(_make_tray_icon())

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        # 标题
        title = QLabel("VoiceType")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #f0f0f0;")
        subtitle = QLabel("语音输入设置")
        subtitle.setObjectName("subtitle")
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addSpacing(6)

        # 卡片 1: 引擎选择
        engine_card = QGroupBox("引擎选择")
        elayout = QVBoxLayout(engine_card)

        self._engine_combo = QComboBox()
        self._engine_combo.addItem("阿里云 Paraformer（云端）", "alibaba")
        self._engine_combo.addItem("faster-whisper（本地）", "local")
        self._engine_combo.currentIndexChanged.connect(self._on_engine_switch)
        elayout.addWidget(self._engine_combo)

        # 本地模型设置（默认隐藏）
        self._local_widget = QWidget()
        llayout = QVBoxLayout(self._local_widget)
        llayout.setContentsMargins(0, 0, 0, 0)
        llayout.setSpacing(8)
        self._model_combo = QComboBox()
        self._model_combo.addItems(["tiny (39MB)", "base (74MB)", "small (244MB)"])
        self._model_combo.setCurrentIndex(1)  # base
        llayout.addWidget(self._model_combo)
        self._download_btn = QPushButton("下载模型")
        self._download_btn.setObjectName("accent")
        self._download_btn.clicked.connect(self._download_model)
        llayout.addWidget(self._download_btn)
        elayout.addWidget(self._local_widget)
        self._local_widget.hide()

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.hide()
        elayout.addWidget(self._progress_bar)

        root.addWidget(engine_card)

        # 卡片 2: API 配置
        self._api_card = QGroupBox("API 配置")
        alayout = QVBoxLayout(self._api_card)

        self._api_input = QLineEdit()
        self._api_input.setPlaceholderText("输入阿里云 DashScope API Key")
        self._api_input.setEchoMode(QLineEdit.Password)
        self._api_input.textChanged.connect(self._on_api_key_changed)
        alayout.addWidget(self._api_input)

        self._api_status = QLabel("")
        self._api_status.setObjectName("status")
        alayout.addWidget(self._api_status)

        root.addWidget(self._api_card)

        # 卡片 3: 快捷键
        hotkey_card = QGroupBox("快捷键")
        hlayout = QVBoxLayout(hotkey_card)

        hrow = QHBoxLayout()
        self._hotkey_btn = QPushButton(self._hotkey_display())
        self._hotkey_btn.setMinimumHeight(44)
        self._hotkey_btn.clicked.connect(self._record_hotkey)
        hrow.addWidget(self._hotkey_btn)

        self._clear_hotkey_btn = QPushButton("清除")
        self._clear_hotkey_btn.clicked.connect(self._clear_hotkey)
        hrow.addWidget(self._clear_hotkey_btn)
        hlayout.addLayout(hrow)

        root.addWidget(hotkey_card)

        root.addStretch()

        # 底部状态
        self._status_label = QLabel("")
        self._status_label.setObjectName("status")
        root.addWidget(self._status_label)

    def _init_tray(self):
        """系统托盘"""
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_make_tray_icon())
        self._tray.setToolTip("VoiceType — 语音输入")

        menu = QMenu()
        show_action = QAction("显示设置", self)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)
        menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    # ---------- 引擎 ----------

    def _create_engine(self):
        engine_type = self._config["engine"]
        if engine_type == "alibaba":
            engine = AlibabaEngine(api_key=self._config.get("alibaba_api_key", ""))
            engine.initialize()
        else:
            size = self._config.get("local_model", "base")
            engine = LocalEngine(model_size=size)
            engine.initialize()
        self._engine = engine
        self.engine_changed.emit(self._engine)

    # ---------- 配置应用 ----------

    def _apply_config(self):
        # 引擎选择
        engine = self._config.get("engine", "alibaba")
        idx = self._engine_combo.findData(engine)
        if idx >= 0:
            self._engine_combo.setCurrentIndex(idx)

        # API Key
        api_key = self._config.get("alibaba_api_key", "")
        self._api_input.setText(api_key)

        # 本地模型
        local = self._config.get("local_model", "base")
        sizes = ["tiny", "base", "small"]
        idx2 = sizes.index(local) if local in sizes else 1
        self._model_combo.setCurrentIndex(idx2)

        # 引擎初始状态
        if engine == "alibaba":
            self._local_widget.hide()
            self._progress_bar.hide()
            self._api_card.show()
            self._api_input.setEnabled(True)
        else:
            self._local_widget.show()
            self._progress_bar.hide()
            self._api_card.hide()
            # 检查模型是否已下载
            self._check_model_status()

    # ---------- 事件处理 ----------

    def _on_engine_switch(self, index):
        engine_type = self._engine_combo.currentData()
        self._config["engine"] = engine_type
        save_config(self._config)

        if engine_type == "local":
            self._local_widget.show()
            self._progress_bar.hide()
            self._api_card.hide()
            self._check_model_status()
        else:
            self._local_widget.hide()
            self._progress_bar.hide()
            self._api_card.show()
            self._api_input.setEnabled(True)

        self._create_engine()
        self._update_status()

    def _check_model_status(self):
        """检查本地模型是否已下载"""
        from engine.local_engine import LocalEngine, WHISPER_MODELS, MODEL_DIR
        import os

        model_size = self._model_combo.currentData()
        model_name = WHISPER_MODELS.get(model_size, "base")
        model_path = os.path.join(MODEL_DIR, f"models--Systran--faster-whisper-{model_name}")

        if os.path.exists(model_path):
            self._download_btn.setText("重新下载")
            self._status_label.setText("模型已就绪，可以开始使用")
        else:
            self._download_btn.setText("下载模型")
            self._status_label.setText("请先下载模型")

    def _on_api_key_changed(self, text):
        self._config["alibaba_api_key"] = text
        save_config(self._config)
        if self._config["engine"] == "alibaba":
            self._create_engine()
            self._update_status()
        # 简单的输入提示
        if text and len(text) > 10:
            self._api_status.setText("API Key 已填写")
        elif text:
            self._api_status.setText("")
        else:
            self._api_status.setText("")

    def _download_model(self):
        size_index = self._model_combo.currentIndex()
        sizes = ["tiny", "base", "small"]
        model_size = sizes[size_index]

        self._config["local_model"] = model_size
        save_config(self._config)

        self._downloading = True
        self._download_btn.setEnabled(False)
        self._download_btn.setText("下载中...")
        self._progress_bar.setValue(0)
        self._progress_bar.show()

        self._download_thread = threading.Thread(
            target=self._do_download, args=(model_size,), daemon=True
        )
        self._download_thread.start()

    def _do_download(self, model_size):
        def progress(val, msg):
            # 从后台线程安全地更新 UI
            self.download_progress.emit(val, msg)

        ok = download_model(model_size, progress_callback=progress)

        # 下载完成后更新 UI（必须通过信号）
        if ok:
            self.download_progress.emit(100, "完成")
        else:
            self.download_progress.emit(0, "失败")

    def _update_download_progress(self, val, msg):
        """在主线程更新下载进度（由信号触发）"""
        self._progress_bar.setValue(val)
        self._status_label.setText(f"下载模型: {msg}")

        # 下载完成时的处理
        if val == 100:
            self._progress_bar.hide()
            self._download_btn.setEnabled(True)
            self._download_btn.setText("重新下载")
            self._downloading = False
            self._status_label.setText("模型已就绪，可以开始使用")
            self._create_engine()
        elif val == 0 and msg == "失败":
            self._progress_bar.hide()
            self._download_btn.setEnabled(True)
            self._download_btn.setText("下载模型")
            self._downloading = False
            self._status_label.setText("下载失败，请检查网络")

    def _record_hotkey(self):
        self._hotkey_btn.setText("按下快捷键组合...")
        self._hotkey_btn.setStyleSheet("border-color: #22c55e; color: #22c55e;")

        # 停止当前监听
        self._hotkey.stop()

        def on_done(keys):
            if len(keys) >= 2:  # 至少一个修饰键 + 一个字符键
                self._config["hotkey"] = keys
                save_config(self._config)
                self._hotkey.set_hotkey(keys)
            self._hotkey_btn.setText(self._hotkey_display())
            self._hotkey_btn.setStyleSheet("")
            # 重启监听
            self._hotkey.start()

        from hotkey_manager import HotkeyManager
        self._record_listener = HotkeyManager.record_key_sequence(on_done)

    def _clear_hotkey(self):
        self._config["hotkey"] = []
        save_config(self._config)
        self._hotkey_btn.setText("点击设置快捷键")
        self._hotkey.set_hotkey([])

    def _hotkey_display(self):
        keys = self._config.get("hotkey", [])
        if not keys:
            return "点击设置快捷键"
        return " + ".join(k.upper() for k in keys)

    def _update_status(self):
        if self._engine and self._engine.is_available():
            self._status_label.setText(f"引擎就绪: {self._engine.name}")
        else:
            self._status_label.setText("引擎未就绪，请配置 API Key 或下载本地模型")

    # ---------- 托盘 ----------

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_window()

    def _show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit_app(self):
        self._hotkey.stop()
        self._tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self._tray.showMessage(
            "VoiceType",
            "已最小化到系统托盘，快捷键仍然可用",
            QSystemTrayIcon.Information,
            2000,
        )
