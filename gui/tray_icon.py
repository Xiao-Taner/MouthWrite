"""系统托盘图标，提供设置入口和退出功能。"""

from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Signal, Qt


class TrayIcon(QSystemTrayIcon):
    """系统托盘图标：右键菜单包含「设置」和「退出」。"""

    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._create_icon()
        self._create_menu()
        self.setToolTip("MouthWrite — AI 语音输入法\n长按快捷键开始语音输入")

    def _create_icon(self):
        """生成一个简单的程序图标（蓝底白字 T）。"""
        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景圆角矩形
        painter.setBrush(QColor("#89b4fa"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(4, 4, size - 8, size - 8, 14, 14)

        # 文字
        painter.setPen(QColor("#1e1e2e"))
        font = QFont("Segoe UI", 30, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "T")

        painter.end()
        self.setIcon(QIcon(pixmap))

    def _create_menu(self):
        menu = QMenu()
        menu.setStyleSheet(
            """
            QMenu {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #45475a;
            }
            """
        )

        action_settings = menu.addAction("⚙  设置")
        action_settings.triggered.connect(self.settings_requested.emit)

        menu.addSeparator()

        action_quit = menu.addAction("✖  退出")
        action_quit.triggered.connect(self.quit_requested.emit)

        self.setContextMenu(menu)
