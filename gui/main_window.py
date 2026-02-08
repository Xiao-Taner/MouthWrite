"""浮动转录窗口 —— 屏幕底部中央弹出，分段显示转录/优化/翻译结果。

设计原则：
  · 纯文字，不使用任何 emoji / 图标
  · 分段间用细分割线隔开
  · "已复制" 提示显示在对应段落标题行右侧
  · 窗口高度通过 fontMetrics 精确计算，紧贴内容
"""

import html as _html_mod

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGraphicsDropShadowEffect,
    QFrame,
    QSizePolicy,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QCursor, QTextDocument

# 行距百分比（160% 相比默认 ~120% 有明显但舒适的间距提升）
_LINE_HEIGHT = 160


# ═══════════════════════════════════════════════════════════════
#  TextBlock — 单段文本（标题 + 内容 + 可选"已复制"）
# ═══════════════════════════════════════════════════════════════
class TextBlock(QWidget):
    STYLES = {
        "asr":       {"color": "#7f849c", "title": "原始转录"},
        "optimize":  {"color": "#89b4fa", "title": "优化结果"},
        "translate": {"color": "#a6e3a1", "title": "翻译结果"},
    }

    _TITLE_H = 16       # 标题行固定高度
    _PADDING_V = 6       # 上下内边距
    _TITLE_SPACING = 4   # 标题与正文间距

    def __init__(self, block_type: str, parent=None):
        super().__init__(parent)
        s = self.STYLES.get(block_type, self.STYLES["asr"])
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, self._PADDING_V, 0, self._PADDING_V)
        lay.setSpacing(self._TITLE_SPACING)

        # 标题行：标题 ... 已复制
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = QLabel(s["title"])
        title.setStyleSheet(
            f"color: {s['color']}; font-size: 11px; font-weight: bold;"
            " background: transparent;"
        )
        title.setFixedHeight(self._TITLE_H)
        title_row.addWidget(title)
        title_row.addStretch()

        self._copied_label = QLabel("已复制")
        self._copied_label.setStyleSheet(
            "color: #a6e3a1; font-size: 11px; font-weight: bold;"
            " background: transparent;"
        )
        self._copied_label.setFixedHeight(self._TITLE_H)
        self._copied_label.hide()
        title_row.addWidget(self._copied_label)
        lay.addLayout(title_row)

        # 正文 — 使用 RichText 以支持自定义 line-height
        self._plain_text = ""
        self._text = QLabel("")
        self._text.setWordWrap(True)
        self._text.setTextFormat(Qt.TextFormat.RichText)
        self._text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._text.setStyleSheet(
            "color: #cdd6f4; font-size: 14px;"
            ' font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;'
            " background: transparent;"
        )
        self._text.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        lay.addWidget(self._text)

    # -- 内部渲染 --
    def _render(self):
        """将纯文本转为带 line-height 的富文本并显示。"""
        if not self._plain_text:
            self._text.setText("")
            return
        escaped = _html_mod.escape(self._plain_text).replace("\n", "<br>")
        self._text.setText(
            f'<div style="line-height: {_LINE_HEIGHT}%;">{escaped}</div>'
        )

    # -- 公共接口 --
    def set_text(self, text: str):
        self._plain_text = text
        self._render()

    def append_text(self, text: str):
        self._plain_text += text
        self._render()

    def get_text(self) -> str:
        return self._plain_text

    def show_copied(self):
        self._copied_label.show()
        QTimer.singleShot(3000, self._copied_label.hide)

    def calc_text_height(self, available_width: int) -> int:
        """用 QTextDocument 精确计算富文本（含 line-height）正文高度。"""
        text = self._plain_text
        fm = self._text.fontMetrics()
        if not text:
            return int(fm.height() * _LINE_HEIGHT / 100)
        escaped = _html_mod.escape(text).replace("\n", "<br>")
        doc = QTextDocument()
        doc.setDefaultFont(self._text.font())
        doc.setTextWidth(available_width)
        doc.setHtml(
            f'<div style="line-height: {_LINE_HEIGHT}%;">{escaped}</div>'
        )
        return int(doc.size().height())

    def calc_block_height(self, available_width: int) -> int:
        """整个块的高度 = 上下 padding + 标题行 + 间距 + 正文高度。"""
        return (
            self._PADDING_V * 2
            + self._TITLE_H
            + self._TITLE_SPACING
            + self.calc_text_height(available_width)
        )


# ═══════════════════════════════════════════════════════════════
#  FloatingWindow — 主浮动窗口
# ═══════════════════════════════════════════════════════════════
class FloatingWindow(QWidget):
    translate_clicked = Signal()
    window_closed = Signal()

    STATE_LISTENING = "listening"
    STATE_RECOGNIZING = "recognizing"
    STATE_OPTIMIZING = "optimizing"
    STATE_DONE = "done"
    STATE_TRANSLATING = "translating"
    STATE_ERROR = "error"

    _MAX_H = 520
    _WIDTH = 620

    # 布局常量 —— 对应 _setup_ui 中的边距 / 间距值
    _OUTER_MARGIN = 10        # 外层 layout 上下左右
    _INNER_MARGIN_V = 10      # 容器内部上下
    _INNER_MARGIN_H = 14      # 容器内部左右
    _INNER_SPACING = 6        # 容器内部 spacing
    _STATUS_H = 18            # 状态栏固定高度
    _BORDER = 2               # border 1px * 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state: str | None = None
        self._blocks: dict[str, TextBlock] = {}
        self._dividers: list[QFrame] = []
        self._translated = False

        # 防抖定时器
        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.setInterval(60)
        self._reflow_timer.timeout.connect(self._reposition)

        self._setup_window()
        self._setup_ui()

    # ── 窗口属性 ─────────────────────────────────────────
    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(self._WIDTH)

    # ── 构建 UI ──────────────────────────────────────────
    def _setup_ui(self):
        # 容器
        self._container = QWidget(self)
        self._container.setObjectName("container")
        self._container.setStyleSheet("""
            #container {
                background-color: #272727;
                border-radius: 10px;
                border: 1px solid #383838;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self._container)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 90))
        shadow.setOffset(0, 3)
        self._container.setGraphicsEffect(shadow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            self._OUTER_MARGIN, self._OUTER_MARGIN,
            self._OUTER_MARGIN, self._OUTER_MARGIN,
        )
        outer.addWidget(self._container)

        self._inner = QVBoxLayout(self._container)
        self._inner.setContentsMargins(
            self._INNER_MARGIN_H, self._INNER_MARGIN_V,
            self._INNER_MARGIN_H, self._INNER_MARGIN_V,
        )
        self._inner.setSpacing(self._INNER_SPACING)

        # 状态栏 — 固定一行高度
        self._status_label = QLabel("正在聆听...")
        self._status_label.setStyleSheet(
            "color: #a6adc8; font-size: 12px; background: transparent;"
        )
        self._status_label.setFixedHeight(self._STATUS_H)
        self._inner.addWidget(self._status_label)

        # 文本块区域 — QScrollArea 支持内容过长时滚动
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QWidget#_scrollWidget { background: transparent; }
            QScrollBar:vertical {
                background: transparent; width: 6px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #585858; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #6c6c6c; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
        # viewport 也要透明
        self._scroll_area.viewport().setStyleSheet("background: transparent;")

        self._scroll_widget = QWidget()
        self._scroll_widget.setObjectName("_scrollWidget")
        self._blocks_layout = QVBoxLayout(self._scroll_widget)
        self._blocks_layout.setContentsMargins(0, 0, 0, 0)
        self._blocks_layout.setSpacing(0)

        self._scroll_area.setWidget(self._scroll_widget)
        self._inner.addWidget(self._scroll_area, 1)  # stretch=1 占满剩余空间

        # 滚动条范围变化时自动滚到底部（流式输出跟随最新内容）
        self._auto_scroll = True
        self._scroll_area.verticalScrollBar().rangeChanged.connect(
            self._on_scroll_range_changed
        )

        # 底部栏（翻译按钮）
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 4, 0, 0)
        bottom_row.addStretch()
        self._translate_btn = QPushButton("翻译")
        self._translate_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._translate_btn.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa; color: #1e1e2e; border: none;
                border-radius: 5px; padding: 5px 16px;
                font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #74c7ec; }
            QPushButton:pressed { background-color: #89dceb; }
            QPushButton:disabled { background-color: #45475a; color: #6c7086; }
        """)
        self._translate_btn.setVisible(False)
        self._translate_btn.clicked.connect(self.translate_clicked.emit)
        bottom_row.addWidget(self._translate_btn)
        self._inner.addLayout(bottom_row)

    # ═══════════════════════════════════════════════════════
    #  Block 管理
    # ═══════════════════════════════════════════════════════
    def add_block(self, block_type: str) -> TextBlock:
        if self._blocks:
            div = QFrame(self)
            div.setFixedHeight(1)
            div.setStyleSheet("background-color: #383838;")
            self._blocks_layout.addWidget(div)
            self._dividers.append(div)

        block = TextBlock(block_type, self)
        self._blocks[block_type] = block
        self._blocks_layout.addWidget(block)
        self._defer_reflow()
        return block

    def append_to_block(self, block_type: str, text: str):
        block = self._blocks.get(block_type)
        if block:
            block.append_text(text)
            self._defer_reflow()

    def set_block_text(self, block_type: str, text: str):
        block = self._blocks.get(block_type)
        if block:
            block.set_text(text)
            self._defer_reflow()

    def get_block_text(self, block_type: str) -> str:
        block = self._blocks.get(block_type)
        return block.get_text() if block else ""

    def show_block_copied(self, block_type: str):
        block = self._blocks.get(block_type)
        if block:
            block.show_copied()

    def clear_blocks(self):
        for b in self._blocks.values():
            self._blocks_layout.removeWidget(b)
            b.deleteLater()
        for d in self._dividers:
            self._blocks_layout.removeWidget(d)
            d.deleteLater()
        self._blocks.clear()
        self._dividers.clear()
        self._translated = False

    # ═══════════════════════════════════════════════════════
    #  状态
    # ═══════════════════════════════════════════════════════
    def set_state(self, state: str):
        self._state = state
        labels = {
            self.STATE_LISTENING:   "正在聆听...",
            self.STATE_RECOGNIZING: "正在识别...",
            self.STATE_OPTIMIZING:  "正在优化文字...",
            self.STATE_DONE:        "已完成",
            self.STATE_TRANSLATING: "正在翻译...",
            self.STATE_ERROR:       "出错了",
        }
        self._status_label.setText(labels.get(state, state))
        show_btn = state == self.STATE_DONE and not self._translated
        self._translate_btn.setVisible(show_btn)
        self._translate_btn.setEnabled(show_btn)

    @property
    def state(self) -> str | None:
        return self._state

    def set_status_text(self, text: str):
        self._status_label.setText(text)

    def mark_translated(self):
        self._translated = True
        self._translate_btn.setVisible(False)

    # ═══════════════════════════════════════════════════════
    #  弹出 & 定位
    # ═══════════════════════════════════════════════════════
    def show_at_bottom_center(self):
        self.show()
        self.raise_()
        self._reposition()

    def _defer_reflow(self):
        # 内容正在变化，乐观地启用自动滚动；_reposition 会根据实际高度修正
        self._auto_scroll = True
        self._reflow_timer.start()

    def _reposition(self):
        """通过 fontMetrics 精确计算内容高度，底边锚定屏幕底部。

        当内容高度超过 _MAX_H 时，窗口固定为 _MAX_H，QScrollArea 自动出现滚动条。
        """
        # 正文可用宽度 = 窗口 - 外层margin*2 - 内层margin*2 - border*2 - 滚动条预留
        text_w = (
            self._WIDTH
            - self._OUTER_MARGIN * 2
            - self._INNER_MARGIN_H * 2
            - self._BORDER
            - 8  # 滚动条宽度预留
        )

        # 固定区域高度（状态栏 + 边距 + 按钮等）
        chrome_h = 0
        chrome_h += self._INNER_MARGIN_V      # 内部上边距
        chrome_h += self._STATUS_H             # 状态栏
        chrome_h += self._INNER_SPACING        # spacing
        # （scroll area 在中间，高度可变）
        chrome_h += self._INNER_SPACING        # spacing
        if self._translate_btn.isVisible():
            chrome_h += 30 + 4                 # 按钮高度 + top margin
        chrome_h += self._INNER_MARGIN_V       # 内部下边距
        chrome_h += self._OUTER_MARGIN * 2     # 外层上下边距
        chrome_h += self._BORDER               # 边框

        # 文本块自然高度
        content_h = 0
        first = True
        for block in self._blocks.values():
            if not first:
                content_h += 1  # 分割线
            first = False
            content_h += block.calc_block_height(text_w)

        ideal_h = chrome_h + content_h
        h = max(60, min(ideal_h, self._MAX_H))
        self.setFixedHeight(h)

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + geo.height() - h - 24
        self.move(x, y)

        # 内容不超限时关闭自动滚动；超限时保持并显式补一次滚动
        if ideal_h <= self._MAX_H:
            self._auto_scroll = False
        else:
            # _reposition 改变窗口高度后，布局可能尚未更新完毕，
            # 此处延迟确保 Qt 先完成布局再滚动（兜底 rangeChanged 信号未触发的情况）
            QTimer.singleShot(15, self._scroll_to_bottom)

    def _on_scroll_range_changed(self, _min: int, _max: int):
        """滚动条范围变化时，若处于自动滚动状态则滚到底部。"""
        if self._auto_scroll and _max > 0:
            self._scroll_area.verticalScrollBar().setValue(_max)

    def _scroll_to_bottom(self):
        """将滚动区域滚到底部。"""
        vbar = self._scroll_area.verticalScrollBar()
        if vbar.maximum() > 0:
            vbar.setValue(vbar.maximum())

    # ═══════════════════════════════════════════════════════
    #  事件
    # ═══════════════════════════════════════════════════════
    def keyPressEvent(self, event):
        self.close()

    def closeEvent(self, event):
        self.window_closed.emit()
        super().closeEvent(event)
