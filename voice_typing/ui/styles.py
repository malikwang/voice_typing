"""暗黑主题 QSS 样式表 — 参考 wooho.cc 极简风格"""

DARK_STYLE = """
/* 全局 */
QWidget {
    background-color: #0d0d0d;
    color: #f0f0f0;
    font-family: "Ubuntu", "Noto Sans CJK SC", sans-serif;
    font-size: 14px;
}

/* 输入框 */
QLineEdit {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 6px;
    padding: 8px 12px;
    color: #f0f0f0;
    selection-background-color: #22c55e;
    selection-color: #0d0d0d;
}
QLineEdit:focus {
    border-color: #22c55e;
}

/* 按钮 */
QPushButton {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 6px;
    padding: 8px 16px;
    color: #f0f0f0;
}
QPushButton:hover {
    border-color: #22c55e;
}
QPushButton:pressed {
    background: #222;
}
QPushButton#accent {
    background: #22c55e;
    color: #0d0d0d;
    border: none;
    font-weight: bold;
}
QPushButton#accent:hover {
    background: #16a34a;
}
QPushButton#danger {
    background: transparent;
    border: 1px solid #ef4444;
    color: #ef4444;
}
QPushButton#danger:hover {
    background: #ef4444;
    color: #0d0d0d;
}

/* 下拉框 */
QComboBox {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 6px;
    padding: 8px 12px;
    color: #f0f0f0;
    min-height: 20px;
}
QComboBox:hover { border-color: #22c55e; }
QComboBox::drop-down { border: none; width: 30px; }
QComboBox::down-arrow { image: none; border: none; }
QComboBox QAbstractItemView {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 6px;
    selection-background-color: #22c55e;
    selection-color: #0d0d0d;
    padding: 4px;
}

/* 进度条 */
QProgressBar {
    border: none;
    border-radius: 4px;
    background: #1a1a1a;
    text-align: center;
    color: #f0f0f0;
    height: 8px;
    font-size: 12px;
}
QProgressBar::chunk {
    background: #22c55e;
    border-radius: 4px;
}

/* 分组卡片 */
QGroupBox {
    border: 1px solid #222;
    border-radius: 10px;
    margin-top: 26px;
    padding: 24px 16px 16px 16px;
    font-weight: bold;
    font-size: 13px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
    color: #888;
}

/* 复选框 */
QCheckBox, QRadioButton {
    spacing: 8px;
    color: #f0f0f0;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #444;
    border-radius: 4px;
    background: #1a1a1a;
}
QCheckBox::indicator:checked {
    background: #22c55e;
    border-color: #22c55e;
    image: url(voice_typing/ui/resources/checkmark.svg);
}

/* 单选按钮 */
QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #444;
    border-radius: 9px;
    background: #1a1a1a;
}
QRadioButton::indicator:checked {
    background: #22c55e;
    border-color: #22c55e;
}

/* 标签 */
QLabel {
    background: transparent;
    color: #f0f0f0;
}
QLabel#subtitle {
    color: #888;
    font-size: 13px;
}
QLabel#status {
    color: #22c55e;
    font-size: 13px;
}
QLabel#error {
    color: #ef4444;
    font-size: 13px;
}

/* 分割线 */
QFrame#separator {
    border: none;
    border-top: 1px solid #222;
    max-height: 1px;
}

/* 滚动条 — 不滑动时隐藏，hover 时出现 */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: rgba(51, 51, 51, 0);
    border-radius: 3px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover,
QScrollBar:vertical:hover QScrollBar::handle:vertical {
    background: rgba(51, 51, 51, 200);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

/* 工具提示 */
QToolTip {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 6px;
    padding: 6px 10px;
    color: #f0f0f0;
    font-size: 13px;
}
"""

OVERLAY_STYLE = """
QWidget#overlay {
    background: rgba(13, 13, 13, 0.88);
    border: 1px solid #333;
    border-radius: 12px;
}
QLabel#transcript {
    background: transparent;
    color: #f0f0f0;
    font-size: 18px;
    padding: 16px 24px;
}
QLabel#indicator {
    background: #22c55e;
    border-radius: 5px;
    min-width: 10px;
    max-width: 10px;
    min-height: 10px;
    max-height: 10px;
}
"""
