"""MouthWrite — AI 语音输入法入口。

双击运行后常驻系统托盘，长按快捷键（默认 RAlt）即可语音输入。
"""

import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from config import Config
from core.controller import Controller
from gui.main_window import FloatingWindow
from gui.settings_dialog import SettingsDialog
from gui.tray_icon import TrayIcon


class MouthWriteApp:
    """应用主类，负责初始化各组件并连接信号。"""

    def __init__(self):
        # 高 DPI 支持（必须在 QApplication 创建之前设置）
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        self._app = QApplication(sys.argv)
        self._app.setApplicationName("MouthWrite")
        self._app.setQuitOnLastWindowClosed(False)

        self._config = Config()

        # 核心组件
        self._window = FloatingWindow()
        self._controller = Controller(self._window)
        self._tray = TrayIcon()

        # 托盘信号
        self._tray.settings_requested.connect(self._show_settings)
        self._tray.quit_requested.connect(self._quit)

        # 启动
        self._tray.show()
        self._tray.showMessage(
            "MouthWrite 已启动",
            f"长按 {self._config.get('hotkey', 'RAlt').upper()} 开始语音输入",
            TrayIcon.MessageIcon.Information,
            2000,
        )
        self._controller.start()

    # ── 托盘操作 ─────────────────────────────────────────────────────
    def _show_settings(self):
        dialog = SettingsDialog(self._config)
        if dialog.exec():
            # 设置保存成功，通知控制器更新热键
            self._controller.update_hotkey()

    def _quit(self):
        self._controller.stop()
        self._tray.hide()
        self._app.quit()

    # ── 运行 ─────────────────────────────────────────────────────────
    def run(self) -> int:
        return self._app.exec()


def main():
    app = MouthWriteApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
