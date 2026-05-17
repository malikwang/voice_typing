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
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # 组件
        self._indicator = StatusIndicator()
        self._waveform = WaveformWidget()
        self._waveform.hide()  # 初始隐藏

        self._text_label = QLabel("")
        self._text_label.setStyleSheet(
            "color: #f0f0f0; font-size: 15px; background: transparent; padding: 0px;"
        )
        self._text_label.setWordWrap(True)
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
        """平滑过渡到新尺寸"""
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - width) // 2
        y = screen.bottom() - height - 60

        start_rect = self.geometry()
        end_rect = QRect(x, y, width, height)

        self._size_animation.setStartValue(start_rect)
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
        self._text_label.hide()
        self._waveform.start()
        self._set_recording_size()

    def stop_recording(self):
        """停止录音：圆球变绿 + 隐藏波形"""
        self._indicator.set_recording(False)
        self._waveform.stop()

    def set_text(self, text: str):
        """设置文字，自动调整窗口大小"""
        if not text:
            return

        # 隐藏波形，显示文字
        self._waveform.hide()
        self._text_label.setText(text)
        self._text_label.show()

        # 计算文字所需宽度
        font = QFont("Sans", 15)
        metrics = QFontMetrics(font)
        screen_width = QApplication.primaryScreen().availableGeometry().width()

        text_width = metrics.horizontalAdvance(text)
        max_width = int(screen_width * 0.6)
        min_width = 200

        # 计算窗口宽度
        total_width = text_width + 56 + 32  # 文字 + 圆球 + 边距
        if total_width < min_width:
            width = min_width
        elif total_width > max_width:
            width = max_width
        else:
            width = total_width

        # 计算高度（考虑换行）
        text_rect = metrics.boundingRect(
            0, 0, width - 56 - 32, 1000,
            Qt.TextWordWrap | Qt.AlignLeft,
            text
        )
        height = max(64, text_rect.height() + 24)

        self._animate_to_size(width, height)

    def reset(self):
        """重置到待机状态"""
        self._indicator.set_recording(False)
        self._waveform.stop()
        self._text_label.hide()
        self._text_label.setText("")
        self._set_idle_size()
