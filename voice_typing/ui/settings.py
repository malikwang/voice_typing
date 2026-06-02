"""设置主窗口"""

import subprocess
import threading
import os

from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QByteArray
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QComboBox, QPushButton, QProgressBar,
    QSystemTrayIcon, QMenu, QAction, QApplication, QMessageBox,
    QListWidget, QListWidgetItem, QScrollArea, QCheckBox,
    QRadioButton, QButtonGroup,
)

from voice_typing.core.config import load_config, save_config
from voice_typing.engine.alibaba import AlibabaEngine
from voice_typing.engine.local import LocalEngine, download_model
from voice_typing.engine.mimo import MimoEngine
from voice_typing.engine.volcengine import VolcengineEngine
from voice_typing.core.vocabulary import sync_vocabulary


def _make_tray_icon():
    """加载麦克风图标作为托盘图标"""
    import os
    # 获取图标文件路径（相对于当前文件）
    current_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(current_dir, "image", "20260518-213528.jpg")

    # 如果图标文件存在，使用它；否则使用默认绘制的图标
    if os.path.exists(icon_path):
        pix = QPixmap(icon_path)
        # 缩放到合适的托盘图标尺寸
        pix = pix.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QIcon(pix)
    else:
        # 备用方案：绘制简单的绿色圆形图标
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


def _make_eye_icon(visible=True):
    """生成眼睛图标（SVG）"""
    if visible:
        # 睁眼图标
        svg_data = """
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"
                  fill="#9ca3af"/>
        </svg>
        """
    else:
        # 闭眼图标
        svg_data = """
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z"
                  fill="#9ca3af"/>
        </svg>
        """

    renderer = QSvgRenderer(QByteArray(svg_data.encode()))
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


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
        self.setFixedSize(520, 750)
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

        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        # 滚动内容容器
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(12)

        # 卡片 1: 引擎选择
        engine_card = QGroupBox("引擎选择")
        elayout = QVBoxLayout(engine_card)

        self._engine_combo = QComboBox()
        self._engine_combo.addItem("阿里云 Paraformer（云端）", "alibaba")
        self._engine_combo.addItem("火山引擎 BigModel（云端）- 开发中", "volcengine")
        self._engine_combo.addItem("小米 MiMo Realtime（云端）", "mimo")
        self._engine_combo.addItem("faster-whisper（本地）", "local")
        self._engine_combo.currentIndexChanged.connect(self._on_engine_preview)
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

        scroll_layout.addWidget(engine_card)

        # 卡片 2: API 配置（动态切换：阿里云 / 火山引擎）
        self._api_card = QGroupBox("API 配置")
        alayout = QVBoxLayout(self._api_card)

        # --- 阿里云 API Key 输入（带眼睛按钮） ---
        self._alibaba_api_widget = QWidget()
        api_wrapper = QWidget(self._alibaba_api_widget)
        api_wrapper.setFixedHeight(40)

        self._api_input = QLineEdit(api_wrapper)
        self._api_input.setPlaceholderText("输入阿里云 DashScope API Key")
        self._api_input.setEchoMode(QLineEdit.Password)
        self._api_input.setGeometry(0, 0, 400, 40)
        self._api_input.setStyleSheet("padding-right: 40px;")

        self._eye_btn = QPushButton(api_wrapper)
        self._eye_btn.setIcon(_make_eye_icon(visible=True))
        self._eye_btn.setFixedSize(35, 35)
        self._eye_btn.setStyleSheet("""
            QPushButton { border: none; background: transparent; }
            QPushButton:hover { background: rgba(255, 255, 255, 0.1); border-radius: 4px; }
        """)
        self._eye_btn.setCursor(Qt.PointingHandCursor)
        self._eye_btn.setToolTip("显示/隐藏 API Key")
        self._eye_btn.clicked.connect(self._toggle_api_visibility)

        def resize_api_widgets():
            w = api_wrapper.width()
            self._api_input.setGeometry(0, 0, w, 40)
            self._eye_btn.setGeometry(w - 38, 3, 35, 35)
        api_wrapper.resizeEvent = lambda e: resize_api_widgets()
        resize_api_widgets()

        alibaba_api_layout = QVBoxLayout(self._alibaba_api_widget)
        alibaba_api_layout.setContentsMargins(0, 0, 0, 0)
        alibaba_api_layout.addWidget(api_wrapper)
        alayout.addWidget(self._alibaba_api_widget)

        # --- 火山引擎 API 输入（ASR + 豆包润色） ---
        self._volc_api_widget = QWidget()
        volc_layout = QVBoxLayout(self._volc_api_widget)
        volc_layout.setContentsMargins(0, 0, 0, 0)
        volc_layout.setSpacing(8)

        volc_asr_label = QLabel("语音识别 (ASR)")
        volc_asr_label.setObjectName("subtitle")
        volc_layout.addWidget(volc_asr_label)

        self._volc_app_id_input = QLineEdit()
        self._volc_app_id_input.setPlaceholderText("App ID（X-Api-App-Key）")
        self._volc_app_id_input.setEchoMode(QLineEdit.Password)
        volc_layout.addWidget(self._volc_app_id_input)

        self._volc_access_token_input = QLineEdit()
        self._volc_access_token_input.setPlaceholderText("Access Token（X-Api-Access-Key）")
        self._volc_access_token_input.setEchoMode(QLineEdit.Password)
        volc_layout.addWidget(self._volc_access_token_input)

        volc_llm_label = QLabel("文本润色 (豆包大模型)")
        volc_llm_label.setObjectName("subtitle")
        volc_layout.addWidget(volc_llm_label)

        self._doubao_api_key_input = QLineEdit()
        self._doubao_api_key_input.setPlaceholderText("豆包 ARK API Key")
        self._doubao_api_key_input.setEchoMode(QLineEdit.Password)
        volc_layout.addWidget(self._doubao_api_key_input)

        self._doubao_endpoint_input = QLineEdit()
        self._doubao_endpoint_input.setPlaceholderText("推理接入点 ID（ep-xxxxxxxxxxxx）")
        volc_layout.addWidget(self._doubao_endpoint_input)

        alayout.addWidget(self._volc_api_widget)
        self._volc_api_widget.hide()

        # --- 小米 MiMo API Key 输入 ---
        self._mimo_api_widget = QWidget()
        mimo_layout = QVBoxLayout(self._mimo_api_widget)
        mimo_layout.setContentsMargins(0, 0, 0, 0)
        mimo_layout.setSpacing(8)

        self._mimo_api_key_input = QLineEdit()
        self._mimo_api_key_input.setPlaceholderText("输入 Mify API Key（MIFY_API_KEY）")
        self._mimo_api_key_input.setEchoMode(QLineEdit.Password)
        mimo_layout.addWidget(self._mimo_api_key_input)

        mimo_hint = QLabel("从 llm.mioffice.cn 获取 API Key")
        mimo_hint.setObjectName("subtitle")
        mimo_layout.addWidget(mimo_hint)

        alayout.addWidget(self._mimo_api_widget)
        self._mimo_api_widget.hide()

        self._api_status = QLabel("")
        self._api_status.setObjectName("status")
        alayout.addWidget(self._api_status)

        scroll_layout.addWidget(self._api_card)

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

        scroll_layout.addWidget(hotkey_card)

        # 卡片 3.5: 自动停止
        autostop_card = QGroupBox("自动停止")
        autostop_layout = QVBoxLayout(autostop_card)

        autostop_hint = QLabel("说完话后静默多久自动结束录音")
        autostop_hint.setObjectName("subtitle")
        autostop_layout.addWidget(autostop_hint)

        self._autostop_combo = QComboBox()
        self._autostop_combo.addItem("1.5 秒（快速）", 1.5)
        self._autostop_combo.addItem("2 秒", 2.0)
        self._autostop_combo.addItem("3 秒（推荐）", 3.0)
        self._autostop_combo.addItem("5 秒（长思考）", 5.0)
        self._autostop_combo.addItem("不自动停止（手动按快捷键）", 0)
        autostop_layout.addWidget(self._autostop_combo)

        scroll_layout.addWidget(autostop_card)

        # 卡片 4: 润色设置
        polish_card = QGroupBox("文本润色")
        playout = QVBoxLayout(polish_card)
        playout.setSpacing(6)

        self._polish_enabled_cb = QCheckBox("启用文本润色（ASR 识别后调用大模型优化文本）")
        playout.addWidget(self._polish_enabled_cb)

        self._polish_group = QButtonGroup(self)

        self._polish_light = QRadioButton("轻度 — 仅删明显语气词，一字不改")
        self._polish_medium = QRadioButton("中度 — 删语气词、修正标点，保留原文（推荐）")
        self._polish_strong = QRadioButton("重度 — 删语气词、理顺表达、修正标点")

        self._polish_group.addButton(self._polish_light, 0)
        self._polish_group.addButton(self._polish_medium, 1)
        self._polish_group.addButton(self._polish_strong, 2)

        playout.addWidget(self._polish_light)
        playout.addWidget(self._polish_medium)
        playout.addWidget(self._polish_strong)

        self._polish_hint = QLabel("润色强度选择（服务商在上方选择）")
        self._polish_hint.setObjectName("subtitle")
        playout.addWidget(self._polish_hint)

        self._polish_enabled_cb.toggled.connect(self._on_polish_toggled)

        scroll_layout.addWidget(polish_card)

        # 卡片 5: 自定义词库
        vocab_card = QGroupBox("自定义词库")
        vlayout = QVBoxLayout(vocab_card)
        vlayout.setSpacing(8)

        vocab_hint = QLabel("添加专业词汇，ASR 识别和 LLM 润色时会自动修正")
        vocab_hint.setObjectName("subtitle")
        vocab_hint.setWordWrap(True)
        vlayout.addWidget(vocab_hint)

        # 词库列表
        self._vocab_list = QListWidget()
        self._vocab_list.setMaximumHeight(120)
        vlayout.addWidget(self._vocab_list)

        # 输入行: 词汇 + 添加按钮
        term_row = QHBoxLayout()
        self._vocab_term_input = QLineEdit()
        self._vocab_term_input.setPlaceholderText("输入词汇（如：rviz）")
        term_row.addWidget(self._vocab_term_input)

        add_vocab_btn = QPushButton("添加")
        add_vocab_btn.setObjectName("accent")
        add_vocab_btn.setFixedWidth(80)
        add_vocab_btn.clicked.connect(self._add_vocabulary)
        term_row.addWidget(add_vocab_btn)
        vlayout.addLayout(term_row)

        # 删除按钮
        del_vocab_btn = QPushButton("删除选中")
        del_vocab_btn.clicked.connect(self._delete_vocabulary)
        vlayout.addWidget(del_vocab_btn)

        scroll_layout.addWidget(vocab_card)

        # 卡片 6: 开机启动
        autostart_card = QGroupBox("开机启动")
        alayout_auto = QVBoxLayout(autostart_card)
        self._autostart_check = QCheckBox("开机自动启动 VoiceType")
        alayout_auto.addWidget(self._autostart_check)
        scroll_layout.addWidget(autostart_card)

        scroll_layout.addStretch()

        # 将滚动区域添加到主布局
        scroll.setWidget(scroll_content)
        root.addWidget(scroll)

        # 底部按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setMinimumWidth(100)
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)

        self._apply_btn = QPushButton("确定")
        self._apply_btn.setObjectName("accent")
        self._apply_btn.setMinimumWidth(100)
        self._apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self._apply_btn)

        root.addLayout(btn_row)

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
        engine_type = self._config.get("engine", "alibaba")
        if engine_type == "alibaba":
            engine = AlibabaEngine(
                api_key=self._config.get("alibaba_api_key", ""),
                phrase_id=self._config.get("phrase_id", ""),
            )
            engine.initialize()
        elif engine_type == "volcengine":
            engine = VolcengineEngine(
                app_id=self._config.get("volc_asr_app_id", ""),
                access_token=self._config.get("volc_asr_access_token", ""),
            )
            engine.initialize()
        elif engine_type == "mimo":
            engine = MimoEngine(
                api_key=self._config.get("mimo_api_key", ""),
            )
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

        # 阿里云 API Key
        api_key = self._config.get("alibaba_api_key", "")
        self._api_input.setText(api_key)

        # 火山引擎 ASR 凭证
        self._volc_app_id_input.setText(self._config.get("volc_asr_app_id", ""))
        self._volc_access_token_input.setText(self._config.get("volc_asr_access_token", ""))

        # 本地模型
        local = self._config.get("local_model", "base")
        sizes = ["tiny", "base", "small"]
        idx2 = sizes.index(local) if local in sizes else 1
        self._model_combo.setCurrentIndex(idx2)

        # MiMo API Key
        self._mimo_api_key_input.setText(self._config.get("mimo_api_key", ""))

        # 引擎初始状态
        self._local_widget.hide()
        self._progress_bar.hide()
        self._alibaba_api_widget.hide()
        self._volc_api_widget.hide()
        self._mimo_api_widget.hide()

        if engine == "alibaba":
            self._alibaba_api_widget.show()
        elif engine == "volcengine":
            self._volc_api_widget.show()
        elif engine == "mimo":
            self._mimo_api_widget.show()
        else:
            self._local_widget.show()
            self._check_model_status()

        # 自定义词库
        vocab = self._config.get("custom_vocabulary", [])
        self._vocab_list.clear()

        # 兼容旧版纯列表格式
        if isinstance(vocab, dict):
            vocab = list(vocab.values())
            self._config["custom_vocabulary"] = vocab

        for item_data in vocab:
            if isinstance(item_data, dict):
                term = item_data.get("term", "")
            else:
                term = str(item_data)

            list_item = QListWidgetItem(term)
            list_item.setData(Qt.UserRole, {"term": term})
            self._vocab_list.addItem(list_item)

        # 开机自动启动
        self._autostart_check.setChecked(self._config.get("autostart", False))

        # 自动停止超时
        autostop = self._config.get("silence_timeout", 3.0)
        idx_autostop = self._autostop_combo.findData(autostop)
        if idx_autostop >= 0:
            self._autostop_combo.setCurrentIndex(idx_autostop)
        else:
            self._autostop_combo.setCurrentIndex(2)  # 默认 3 秒

        # 润色开关 & 强度
        polish_on = self._config.get("polish_enabled", True)
        self._polish_enabled_cb.setChecked(polish_on)
        self._on_polish_toggled(polish_on)

        strength = self._config.get("polish_strength", "medium")
        btn = {"light": self._polish_light, "medium": self._polish_medium, "strong": self._polish_strong}.get(strength)
        if btn:
            btn.setChecked(True)

        # 豆包润色凭证
        self._doubao_api_key_input.setText(self._config.get("doubao_api_key", ""))
        self._doubao_endpoint_input.setText(self._config.get("doubao_endpoint_id", ""))

    # ---------- 事件处理 ----------

    def _on_polish_toggled(self, checked):
        """润色开关切换时显示/隐藏强度选项"""
        self._polish_light.setVisible(checked)
        self._polish_medium.setVisible(checked)
        self._polish_strong.setVisible(checked)
        self._polish_hint.setVisible(checked)

    def _on_engine_preview(self, index):
        """引擎切换预览（不保存）"""
        engine_type = self._engine_combo.currentData()

        self._local_widget.hide()
        self._progress_bar.hide()
        self._alibaba_api_widget.hide()
        self._volc_api_widget.hide()
        self._mimo_api_widget.hide()

        if engine_type == "local":
            self._local_widget.show()
            self._check_model_status()
        elif engine_type == "volcengine":
            self._volc_api_widget.show()
        elif engine_type == "mimo":
            self._mimo_api_widget.show()
        else:  # alibaba
            self._alibaba_api_widget.show()

    def _on_apply(self):
        """确定按钮：保存配置并应用"""
        # 保存引擎类型
        engine_type = self._engine_combo.currentData()
        self._config["engine"] = engine_type

        # 保存阿里云 API Key
        api_key = self._api_input.text()
        self._config["alibaba_api_key"] = api_key

        # 保存火山引擎 ASR 凭证
        self._config["volc_asr_app_id"] = self._volc_app_id_input.text()
        self._config["volc_asr_access_token"] = self._volc_access_token_input.text()

        # 保存 MiMo API Key
        self._config["mimo_api_key"] = self._mimo_api_key_input.text()

        # 保存本地模型
        size_index = self._model_combo.currentIndex()
        sizes = ["tiny", "base", "small"]
        self._config["local_model"] = sizes[size_index]

        # 保存开机自动启动
        autostart = self._autostart_check.isChecked()
        self._config["autostart"] = autostart
        self._set_autostart(autostart)

        # 保存自动停止超时
        self._config["silence_timeout"] = self._autostop_combo.currentData()

        # 保存润色开关 & 强度
        self._config["polish_enabled"] = self._polish_enabled_cb.isChecked()
        if self._polish_light.isChecked():
            self._config["polish_strength"] = "light"
        elif self._polish_strong.isChecked():
            self._config["polish_strength"] = "strong"
        else:
            self._config["polish_strength"] = "medium"

        # 保存豆包润色凭证
        self._config["doubao_api_key"] = self._doubao_api_key_input.text()
        self._config["doubao_endpoint_id"] = self._doubao_endpoint_input.text()

        # 保存自定义词库
        vocab = []
        hotwords = []  # 仅术语列表，用于 Paraformer 热词 API
        for i in range(self._vocab_list.count()):
            item = self._vocab_list.item(i)
            data = item.data(Qt.UserRole)
            term = data.get("term") if data else item.text()
            vocab.append({"term": term})
            hotwords.append(term)
        self._config["custom_vocabulary"] = vocab

        # 同步热词表到阿里云，获取 phrase_id
        if engine_type == "alibaba" and hotwords and api_key:
            self._status_label.setText("正在同步热词表...")
            QApplication.processEvents()
            phrase_id = sync_vocabulary(
                api_key=api_key,
                hotwords=hotwords,
                phrase_id=self._config.get("phrase_id", ""),
            )
            if phrase_id:
                self._config["phrase_id"] = phrase_id
            else:
                self._status_label.setText("热词同步失败（识别仍可用，热词不生效）")
                QTimer.singleShot(3000, lambda: self._update_status())
        elif not vocab:
            # 热词列表为空，清空 phrase_id
            self._config["phrase_id"] = ""

        # 保存配置文件
        save_config(self._config)

        # 重新创建引擎
        self._create_engine()
        self._update_status()

        # 提示用户
        self._status_label.setText("设置已保存并应用")
        QTimer.singleShot(2000, lambda: self._update_status())

    def _on_cancel(self):
        """取消按钮：恢复到已保存的配置"""
        self._apply_config()
        self._status_label.setText("已恢复到上次保存的设置")
        QTimer.singleShot(2000, lambda: self._update_status())

    def _toggle_api_visibility(self):
        """切换 API Key 显示/隐藏"""
        if self._api_input.echoMode() == QLineEdit.Password:
            self._api_input.setEchoMode(QLineEdit.Normal)
            self._eye_btn.setIcon(_make_eye_icon(visible=False))
        else:
            self._api_input.setEchoMode(QLineEdit.Password)
            self._eye_btn.setIcon(_make_eye_icon(visible=True))

    def _add_vocabulary(self):
        """添加词汇"""
        term = self._vocab_term_input.text().strip()

        if not term:
            self._status_label.setText("请输入词汇")
            QTimer.singleShot(2000, lambda: self._update_status())
            return

        # 检查是否已存在
        for i in range(self._vocab_list.count()):
            item = self._vocab_list.item(i)
            data = item.data(Qt.UserRole)
            if data and data.get("term") == term:
                self._status_label.setText(f"词汇 '{term}' 已存在")
                QTimer.singleShot(2000, lambda: self._update_status())
                return

        item = QListWidgetItem(term)
        item.setData(Qt.UserRole, {"term": term})
        self._vocab_list.addItem(item)

        self._vocab_term_input.clear()
        hint = f"已添加 '{term}'（点击确定保存）"
        self._status_label.setText(hint)
        QTimer.singleShot(2000, lambda: self._update_status())

    def _delete_vocabulary(self):
        """删除选中的词汇"""
        current_item = self._vocab_list.currentItem()
        if current_item:
            data = current_item.data(Qt.UserRole)
            display = current_item.text()
            self._vocab_list.takeItem(self._vocab_list.row(current_item))
            self._status_label.setText(f"已删除 '{display}'（点击确定保存）")
            QTimer.singleShot(2000, lambda: self._update_status())

    def _on_engine_switch(self, index):
        """引擎切换（旧方法，保留用于兼容）"""
        self._on_engine_preview(index)

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
        """API Key 输入提示（不保存）"""
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

        # 下载时保存模型选择
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
            if len(keys) >= 1:
                # 保存快捷键（快捷键需要立即生效）
                self._config["hotkey"] = keys
                save_config(self._config)
                self._hotkey.set_hotkey(keys)
            self._hotkey_btn.setText(self._hotkey_display())
            self._hotkey_btn.setStyleSheet("")
            # 重启监听
            self._hotkey.start()

        from voice_typing.core.hotkey import HotkeyManager
        self._record_listener = HotkeyManager.record_key_sequence(on_done)

    def _clear_hotkey(self):
        self._config["hotkey"] = []
        save_config(self._config)
        self._hotkey_btn.setText("点击设置快捷键")
        self._hotkey.set_hotkey([])

    # pynput KeyCode vk → 显示名称映射（补充无法从系统获取的键名）
    _VK_LABELS = {269025067: "Fn"}

    @classmethod
    def _key_label(cls, s):
        """将配置中的键字符串转为显示名称"""
        if s.startswith("vk:"):
            vk = int(s[3:])
            if vk in cls._VK_LABELS:
                return cls._VK_LABELS[vk]
            return f"Key({vk})"
        return s.upper()

    def _hotkey_display(self):
        keys = self._config.get("hotkey", [])
        if not keys:
            return "点击设置快捷键"
        return " + ".join(self._key_label(k) for k in keys)

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

    AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
    AUTOSTART_FILE = os.path.join(AUTOSTART_DIR, "voice-typing.desktop")

    def _set_autostart(self, enable: bool):
        """创建或移除开机自启动 desktop 文件"""
        if enable:
            os.makedirs(self.AUTOSTART_DIR, exist_ok=True)
            with open(self.AUTOSTART_FILE, "w") as f:
                f.write("""[Desktop Entry]
Type=Application
Name=VoiceType
Exec=/usr/bin/voice-typing
Icon=voice-typing
Terminal=false
Categories=Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
""")
        else:
            if os.path.exists(self.AUTOSTART_FILE):
                os.remove(self.AUTOSTART_FILE)

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
