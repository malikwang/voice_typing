"""屏幕下方浮窗 — 实时显示语音转写文字"""

import random
from PyQt5.QtCore import Qt, QTimer, QRect, QSize, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QFontMetrics, QFont
from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QApplication


class StatusIndicator(QWidget):
    """状态指示器：绿色圆球（待机）/ 红色圆球（录音）"""

    def __init__(self):
        super().__init__()
        self.setFixedSize(24, 24)
        self._recording = False

    def set_recording(self, recording: bool):
        self._recording = recording
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        # 根据状态选择颜色
        if self._recording:
            color = QColor(239, 68, 68)  # 红色
        else:
            color = QColor(34, 197, 94)  # 绿色

        painter.setBrush(QBrush(color))
        painter.drawEllipse(4, 4, 16, 16)


class WaveformWidget(QWidget):
    """波形动画组件"""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(200, 40)
        self.setSizePolicy(self.sizePolicy().Expanding, self.sizePolicy().Fixed)
        self._wave_heights = [0.0] * 15
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_wave)

    def start(self):
        self.show()
        self._timer.start(50)  # 20fps

    def stop(self):
        self._timer.stop()
        self._wave_heights = [0.0] * 15
        self.update()
        self.hide()

    def _update_wave(self):
        # 随机生成波形高度
        for i in range(len(self._wave_heights)):
            target = random.uniform(0.3, 1.0)
            self._wave_heights[i] = self._wave_heights[i] * 0.6 + target * 0.4
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        bar_width = 4
        spacing = 8
        max_height = 30

        for i, height in enumerate(self._wave_heights):
            x = i * (bar_width + spacing)
            h = int(height * max_height)
            y = (self.height() - h) // 2

            # 红色波形
            painter.setBrush(QBrush(QColor(239, 68, 68, 200)))
            painter.drawRoundedRect(x, y, bar_width, h, 2, 2)


class OverlayWindow(QWidget):
    """半透明浮窗，位于屏幕底部中央"""

    def __init__(self):
        super().__init__()
        self.setObjectName("overlay")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # 拖拽相关
        self._dragging = False
        self._drag_position = None
        self._user_moved = False  # 标记用户是否手动移动过窗口

        # 组件
        self._indicator = StatusIndicator()
        self._waveform = WaveformWidget()
        self._waveform.hide()  # 初始隐藏
        self._text_received = False  # 当前录音周期是否已收到文字

        self._text_label = QLabel("")
        self._text_label.setStyleSheet(
            "color: #f0f0f0; font-size: 15px; background: transparent; padding: 0px;"
        )
        self._text_label.setWordWrap(False)
        self._text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._text_label.hide()  # 初始隐藏

        # 布局
        self._content_layout = QHBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)
        self._content_layout.addWidget(self._indicator)
        self._content_layout.addWidget(self._waveform)
        self._content_layout.addWidget(self._text_label)
        self._content_layout.addStretch()

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.addLayout(self._content_layout)

        # 动画
        self._size_animation = QPropertyAnimation(self, b"geometry")
        self._size_animation.setDuration(300)  # 300ms 过渡
        self._size_animation.setEasingCurve(QEasingCurve.OutCubic)

        # 初始化为最小尺寸（只显示绿色圆球）
        self._set_idle_size()
        self._center_on_screen()

    def _set_idle_size(self):
        """待机状态：只显示绿色圆球"""
        self._animate_to_size(56, 48)

    def _set_recording_size(self):
        """录音状态：红色圆球 + 波形"""
        self._animate_to_size(280, 64)

    def _animate_to_size(self, width: int, height: int):
        """平滑过渡到新尺寸，保持用户拖拽后的位置"""
        current_rect = self.geometry()

        if self._user_moved:
            # 用户移动过窗口，保持当前中心点位置
            center_x = current_rect.x() + current_rect.width() // 2
            center_y = current_rect.y() + current_rect.height() // 2
            x = center_x - width // 2
            y = center_y - height // 2
        else:
            # 首次显示或未移动过，居中到屏幕底部
            screen = QApplication.primaryScreen().availableGeometry()
            x = (screen.width() - width) // 2
            y = screen.bottom() - height - 60

        end_rect = QRect(x, y, width, height)
        self._size_animation.setStartValue(current_rect)
        self._size_animation.setEndValue(end_rect)
        self._size_animation.start()

    def _center_on_screen(self):
        """居中到屏幕底部"""
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = screen.bottom() - self.height() - 60
        self.move(x, y)

    def paintEvent(self, event):
        """绘制半透明圆角背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(20, 20, 20, 230)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 24, 24)

    def start_recording(self):
        """开始录音：圆球变红 + 显示波形"""
        self._indicator.set_recording(True)
        self._text_received = False
        self._text_label.hide()
        self._waveform.start()
        self._waveform.show()
        self._set_recording_size()

    def stop_recording(self):
        """停止录音：圆球变绿 + 隐藏波形"""
        self._indicator.set_recording(False)
        self._waveform.stop()

    MAX_LABEL_WIDTH = 600

    def _calc_label_geometry(self, text: str):
        """根据文字计算 label 宽度和对齐方式。
        短文本：左对齐，label 自适应宽度。
        超长文本：右对齐，label 固定最大宽度，显示文字尾部。"""
        fm = QFontMetrics(self._text_label.font())
        text_width = fm.horizontalAdvance(text) + 10

        if text_width <= self.MAX_LABEL_WIDTH:
            self._text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._text_label.setMinimumWidth(0)
            self._text_label.setMaximumWidth(self.MAX_LABEL_WIDTH)
            return text_width, max(64, fm.height() + 24)
        else:
            self._text_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._text_label.setMinimumWidth(self.MAX_LABEL_WIDTH)
            self._text_label.setMaximumWidth(self.MAX_LABEL_WIDTH)
            return self.MAX_LABEL_WIDTH, max(64, fm.height() + 24)

    def update_text(self, text: str):
        """实时更新文字（录音时），首次收到文字后隐藏波形"""
        if not text:
            return

        # 首次收到识别文字 → 隐藏波形，只显示文字
        if not self._text_received:
            self._text_received = True
            self._waveform.stop()
            self._waveform.hide()

        self._text_label.setText(text)
        self._text_label.show()

        label_width, height = self._calc_label_geometry(text)
        width = 24 + 12 + label_width + 32
        self._animate_to_size(width, height)

    def set_text(self, text: str):
        """设置最终文字（录音结束后），隐藏波形"""
        if not text:
            return

        self._waveform.hide()
        self._text_label.setText(text)
        self._text_label.show()

        label_width, height = self._calc_label_geometry(text)
        width = 24 + 12 + label_width + 32
        self._animate_to_size(width, height)

    def reset(self):
        """重置到待机状态"""
        self._indicator.set_recording(False)
        self._waveform.stop()
        self._text_label.hide()
        self._text_label.setText("")
        self._set_idle_size()

    def mousePressEvent(self, event):
        """鼠标按下：记录拖拽起始位置"""
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """鼠标移动：拖拽窗口"""
        if self._dragging and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        """鼠标释放：结束拖拽"""
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self._user_moved = True  # 标记用户已手动移动窗口
            event.accept()
