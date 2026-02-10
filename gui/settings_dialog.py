"""设置对话框 —— 通用 / 语音识别 / 大模型 / 翻译 / 历史记录 五个 Tab。"""

import sys
import winreg
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QCheckBox,
    QComboBox,
    QPushButton,
    QTabWidget,
    QWidget,
    QScrollArea,
    QFrame,
    QSpinBox,
    QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QGuiApplication

from config import Config
from core.history import HistoryManager


# ── 样式常量 ─────────────────────────────────────────────────────────
_DIALOG_STYLE = """
QDialog {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QLabel {
    color: #bac2de;
    font-size: 13px;
}
QLineEdit, QSpinBox, QTextEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 13px;
    selection-background-color: #89b4fa;
}
QLineEdit:focus, QSpinBox:focus, QTextEdit:focus {
    border-color: #89b4fa;
}
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 13px;
}
QComboBox:focus {
    border-color: #89b4fa;
}
QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    selection-background-color: #45475a;
}
QTabWidget::pane {
    border: 1px solid #313244;
    border-radius: 8px;
    background-color: #1e1e2e;
}
QTabBar::tab {
    background: #313244;
    color: #bac2de;
    padding: 8px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-size: 13px;
}
QTabBar::tab:selected {
    background: #45475a;
    color: #cdd6f4;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: transparent; width: 6px;
}
QScrollBar::handle:vertical {
    background: #585b70; border-radius: 3px; min-height: 20px;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical { background: none; }
"""

_BTN_CANCEL_STYLE = """
QPushButton {
    background-color: #45475a; color: #cdd6f4; border: none;
    border-radius: 6px; padding: 8px 22px; font-size: 13px;
}
QPushButton:hover { background-color: #585b70; }
"""

_BTN_SAVE_STYLE = """
QPushButton {
    background-color: #89b4fa; color: #1e1e2e; border: none;
    border-radius: 6px; padding: 8px 22px; font-size: 13px; font-weight: bold;
}
QPushButton:hover { background-color: #74c7ec; }
"""

_BTN_COPY_STYLE = """
QPushButton {
    background-color: #45475a; color: #cdd6f4; border: none;
    border-radius: 4px; padding: 4px 10px; font-size: 11px;
}
QPushButton:hover { background-color: #585b70; }
"""

_BTN_DANGER_STYLE = """
QPushButton {
    background-color: #45475a; color: #f38ba8; border: none;
    border-radius: 6px; padding: 6px 16px; font-size: 12px;
}
QPushButton:hover { background-color: #585b70; }
"""

_STARTUP_RUN_KEY = r"Software\\Microsoft\\Windows\\CurrentVersion\\Run"
_STARTUP_APP_NAME = "MouthWrite"


class SettingsDialog(QDialog):
    """可配置项设置对话框。"""

    def __init__(self, config: Config | None = None, parent=None):
        super().__init__(parent)
        self._config = config or Config()
        self._history = HistoryManager()
        self.setWindowTitle("MouthWrite 设置")
        self.setMinimumSize(560, 440)
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()
        self._load_from_config()

    # ── 构建 UI ──────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)

        tabs = QTabWidget()

        # ────────── 通用 ──────────
        tab_general = QWidget()
        form_general = QFormLayout(tab_general)
        form_general.setContentsMargins(16, 20, 16, 16)
        form_general.setSpacing(12)

        self._hotkey_combo = QComboBox()
        self._hotkey_combo.addItems([
            "alt_r", "alt_l", "ctrl_r", "ctrl_l",
            "f1", "f2", "f3", "f4", "f5", "f6",
            "f7", "f8", "f9", "f10", "f11", "f12",
        ])
        form_general.addRow("触发快捷键:", self._hotkey_combo)

        self._startup_chk = QCheckBox("开机自启")
        form_general.addRow("启动选项:", self._startup_chk)
        tabs.addTab(tab_general, "通用")

        # ────────── 语音识别 ──────────
        tab_asr = QWidget()
        form_asr = QFormLayout(tab_asr)
        form_asr.setContentsMargins(16, 20, 16, 16)
        form_asr.setSpacing(12)

        self._asr_url = QLineEdit()
        self._asr_url.setPlaceholderText("http://localhost:8000/v1")
        form_asr.addRow("ASR 服务地址:", self._asr_url)

        self._asr_model = QLineEdit()
        self._asr_model.setPlaceholderText("Qwen/Qwen3-ASR-1.7B")
        form_asr.addRow("模型名称:", self._asr_model)

        self._asr_key = QLineEdit()
        self._asr_key.setPlaceholderText("EMPTY")
        form_asr.addRow("API Key:", self._asr_key)

        tabs.addTab(tab_asr, "语音识别")

        # ────────── 大模型 ──────────
        tab_llm = QWidget()
        form_llm = QFormLayout(tab_llm)
        form_llm.setContentsMargins(16, 20, 16, 16)
        form_llm.setSpacing(12)

        self._llm_url = QLineEdit()
        self._llm_url.setPlaceholderText("https://api.deepseek.com/v1")
        form_llm.addRow("LLM 服务地址:", self._llm_url)

        self._llm_model = QLineEdit()
        self._llm_model.setPlaceholderText("deepseek-chat")
        form_llm.addRow("模型名称:", self._llm_model)

        self._llm_key = QLineEdit()
        self._llm_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._llm_key.setPlaceholderText("sk-...")
        form_llm.addRow("API Key:", self._llm_key)

        self._ctx_count = QSpinBox()
        self._ctx_count.setRange(0, 20)
        self._ctx_count.setSuffix(" 条")
        form_llm.addRow("历史上下文条数:", self._ctx_count)

        tip = QLabel("留空 API Key 则跳过文字优化；上下文条数为 0 则不注入历史。")
        tip.setStyleSheet("color: #6c7086; font-size: 12px; padding-top: 4px;")
        tip.setWordWrap(True)
        form_llm.addRow("", tip)

        tabs.addTab(tab_llm, "大模型")

        # ────────── 提示词 ──────────
        tab_prompt = QWidget()
        prompt_lay = QVBoxLayout(tab_prompt)
        prompt_lay.setContentsMargins(16, 20, 16, 16)
        prompt_lay.setSpacing(10)

        prompt_label = QLabel("语音转录文本优化提示词：")
        prompt_label.setStyleSheet("color: #bac2de; font-size: 13px;")
        prompt_lay.addWidget(prompt_label)

        self._optimize_rules = QTextEdit()
        self._optimize_rules.setPlaceholderText(
            "留空则使用内置默认规则。这里仅替换优化规则，不影响历史上下文结构。"
        )
        self._optimize_rules.setMinimumHeight(180)
        prompt_lay.addWidget(self._optimize_rules, stretch=1)

        prompt_tip = QLabel(
            "建议仅填写“规则部分”。保存后立即生效，无需重新打包。"
        )
        prompt_tip.setStyleSheet("color: #6c7086; font-size: 12px;")
        prompt_tip.setWordWrap(True)
        prompt_lay.addWidget(prompt_tip)

        tabs.addTab(tab_prompt, "提示词")

        # ────────── 翻译 ──────────
        tab_trans = QWidget()
        form_trans = QFormLayout(tab_trans)
        form_trans.setContentsMargins(16, 20, 16, 16)
        form_trans.setSpacing(12)

        self._trans_lang = QComboBox()
        self._trans_lang.setEditable(True)
        self._trans_lang.addItems([
            "English", "Chinese", "Japanese", "Korean",
            "French", "German", "Spanish", "Russian",
        ])
        form_trans.addRow("翻译目标语言:", self._trans_lang)

        tip2 = QLabel("翻译功能复用大模型配置，点击转录窗口的翻译按钮触发。")
        tip2.setStyleSheet("color: #6c7086; font-size: 12px; padding-top: 4px;")
        form_trans.addRow("", tip2)

        tabs.addTab(tab_trans, "翻译")

        # ────────── 历史记录 ──────────
        tab_history = QWidget()
        hist_lay = QVBoxLayout(tab_history)
        hist_lay.setContentsMargins(12, 12, 12, 12)
        hist_lay.setSpacing(8)

        # 顶部操作栏
        top_row = QHBoxLayout()
        count_label = QLabel("")
        count_label.setStyleSheet("color: #6c7086; font-size: 12px;")
        self._hist_count_label = count_label
        top_row.addWidget(count_label)
        top_row.addStretch()

        btn_clear = QPushButton("清空历史")
        btn_clear.setStyleSheet(_BTN_DANGER_STYLE)
        btn_clear.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_clear.clicked.connect(self._on_clear_history)
        top_row.addWidget(btn_clear)
        hist_lay.addLayout(top_row)

        # 滚动列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self._hist_inner = QWidget()
        self._hist_inner.setStyleSheet("background: transparent;")
        self._hist_layout = QVBoxLayout(self._hist_inner)
        self._hist_layout.setContentsMargins(0, 0, 4, 0)
        self._hist_layout.setSpacing(4)
        self._hist_layout.addStretch()
        scroll.setWidget(self._hist_inner)
        hist_lay.addWidget(scroll, stretch=1)

        tabs.addTab(tab_history, "历史记录")

        root.addWidget(tabs)

        # ────────── 按钮行 ──────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.setStyleSheet(_BTN_CANCEL_STYLE)
        btn_cancel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("保存")
        btn_save.setStyleSheet(_BTN_SAVE_STYLE)
        btn_save.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_save.clicked.connect(self._on_save)

        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

    # ── 数据加载 / 保存 ──────────────────────────────────────────────
    def _load_from_config(self):
        c = self._config
        self._hotkey_combo.setCurrentText(c.get("hotkey", "alt_r"))
        self._startup_chk.setChecked(bool(c.get("startup.enabled", False)))
        self._asr_url.setText(c.get("asr.base_url", ""))
        self._asr_model.setText(c.get("asr.model", ""))
        self._asr_key.setText(c.get("asr.api_key", ""))
        self._llm_url.setText(c.get("llm.base_url", ""))
        self._llm_model.setText(c.get("llm.model", ""))
        self._llm_key.setText(c.get("llm.api_key", ""))
        self._optimize_rules.setPlainText(c.get("optimize.rules", ""))
        self._ctx_count.setValue(c.get("history.context_count", 5))
        self._trans_lang.setCurrentText(
            c.get("translation.target_language", "English")
        )
        self._populate_history()

    def _on_save(self):
        c = self._config
        c.set("hotkey", self._hotkey_combo.currentText())
        c.set("startup.enabled", self._startup_chk.isChecked())
        self._apply_startup_setting(self._startup_chk.isChecked())
        c.set("asr.base_url", self._asr_url.text().strip())
        c.set("asr.model", self._asr_model.text().strip())
        c.set("asr.api_key", self._asr_key.text().strip())
        c.set("llm.base_url", self._llm_url.text().strip())
        c.set("llm.model", self._llm_model.text().strip())
        c.set("llm.api_key", self._llm_key.text())
        c.set("optimize.rules", self._optimize_rules.toPlainText().strip())
        c.set("history.context_count", self._ctx_count.value())
        c.set("translation.target_language",
              self._trans_lang.currentText().strip())
        self.accept()

    # ── 历史记录 Tab ─────────────────────────────────────────────────
    def _populate_history(self):
        """填充历史记录列表。"""
        # 清除旧条目（保留末尾的 stretch）
        while self._hist_layout.count() > 1:
            item = self._hist_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        records = self._history.get_all()
        self._hist_count_label.setText(f"共 {len(records)} 条记录")

        for rec in records:
            card = self._make_history_card(rec)
            idx = self._hist_layout.count() - 1  # 插到 stretch 之前
            self._hist_layout.insertWidget(idx, card)

    def _make_history_card(self, rec: dict) -> QWidget:
        """创建一条历史记录卡片。"""
        card = QWidget()
        card.setStyleSheet(
            "background-color: #313244; border-radius: 6px;"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        # 第一行：时间 ... 复制按钮
        top = QHBoxLayout()
        time_lbl = QLabel(rec.get("time", ""))
        time_lbl.setStyleSheet("color: #6c7086; font-size: 11px;")
        top.addWidget(time_lbl)
        top.addStretch()

        btn_copy = QPushButton("复制")
        btn_copy.setStyleSheet(_BTN_COPY_STYLE)
        btn_copy.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # 复制优化后文本（如有翻译则优先翻译）
        text_to_copy = rec.get("translated_text") or rec.get(
            "optimized_text", ""
        )
        btn_copy.clicked.connect(
            lambda checked=False, t=text_to_copy: self._copy_text(t, btn_copy)
        )
        top.addWidget(btn_copy)
        lay.addLayout(top)

        # 优化后文本
        opt = rec.get("optimized_text", "")
        if opt:
            opt_lbl = QLabel(opt)
            opt_lbl.setWordWrap(True)
            opt_lbl.setStyleSheet(
                "color: #cdd6f4; font-size: 13px; background: transparent;"
            )
            lay.addWidget(opt_lbl)

        # 翻译文本
        trans = rec.get("translated_text", "")
        if trans:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background-color: #45475a;")
            lay.addWidget(sep)

            trans_lbl = QLabel(trans)
            trans_lbl.setWordWrap(True)
            trans_lbl.setStyleSheet(
                "color: #a6e3a1; font-size: 13px; background: transparent;"
            )
            lay.addWidget(trans_lbl)

        return card

    @staticmethod
    def _copy_text(text: str, btn: QPushButton):
        """复制文本到剪贴板，按钮短暂显示"已复制"。"""
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
        old = btn.text()
        btn.setText("已复制")
        btn.setEnabled(False)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: (btn.setText(old), btn.setEnabled(True)))

    def _on_clear_history(self):
        reply = QMessageBox.question(
            self,
            "清空历史",
            "确定清空所有历史记录？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._history.clear()
            self._populate_history()

    # ── 开机自启 ─────────────────────────────────────────────────────
    def _startup_command(self) -> str:
        """生成写入注册表的启动命令。"""
        if getattr(sys, "frozen", False):
            return f"\"{sys.executable}\""
        project_root = Path(__file__).resolve().parents[1]
        main_py = project_root / "main.py"
        return f"\"{sys.executable}\" \"{main_py}\""

    def _apply_startup_setting(self, enabled: bool):
        """写入/移除开机自启注册表项。"""
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                _STARTUP_RUN_KEY,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                if enabled:
                    winreg.SetValueEx(
                        key, _STARTUP_APP_NAME, 0, winreg.REG_SZ, self._startup_command()
                    )
                else:
                    try:
                        winreg.DeleteValue(key, _STARTUP_APP_NAME)
                    except FileNotFoundError:
                        pass
        except OSError:
            QMessageBox.warning(
                self,
                "开机自启",
                "写入开机自启设置失败，请以管理员权限运行或稍后重试。",
            )
