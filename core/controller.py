"""核心控制器 —— 串联热键、录音、ASR、LLM、GUI 的调度中枢。

流程：长按热键 → 录音 → ASR（流式，写入 asr 块）
      → LLM 优化（流式，写入 optimize 块）→ 复制 + 自动粘贴
      → [可选] 用户点击翻译 → LLM 翻译（流式，写入 translate 块）→ 复制

窗口关闭方式：点击窗口外部 / 按任意键 / 再次按热键开始新一轮
"""

from pynput.keyboard import Key as PynputKey, Controller as KbController
from pynput import mouse as pynput_mouse

from PySide6.QtCore import QObject, Signal, Slot, QTimer, QPoint, QRect, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from utils import resource_path

# 音效文件路径（兼容 PyInstaller 打包）
_SOUND_START = resource_path("gui/start.mp3")
_SOUND_END = resource_path("gui/end.mp3")

from config import Config
from core.hotkey import HotkeyListener
from core.audio import AudioRecorder
from core.asr_client import ASRWorker, clean_asr_output
from core.llm_client import (
    LLMWorker,
    OPTIMIZE_PROMPT,
    OPTIMIZE_PROMPT_WITH_HISTORY,
    TRANSLATE_PROMPT,
)
from core.history import HistoryManager
from gui.main_window import FloatingWindow


class Controller(QObject):
    """控制器：监听热键 → 录音 → ASR → LLM 优化 → 剪贴板 + 自动粘贴。"""

    # 线程安全的 dismiss 请求信号（从 pynput 鼠标回调线程发射）
    _mouse_dismiss_requested = Signal()

    def __init__(self, window: FloatingWindow, parent=None):
        super().__init__(parent)

        self._config = Config()
        self._window = window
        self._audio = AudioRecorder(parent=self)
        self._hotkey = HotkeyListener(
            hotkey_name=self._config.get("hotkey", "alt_r"),
            parent=self,
        )

        # 工作线程引用
        self._asr_worker: ASRWorker | None = None
        self._llm_worker: LLMWorker | None = None

        # 文本缓存
        self._asr_buffer = ""
        self._raw_asr_text = ""
        self._optimized_text = ""

        # 状态
        self._busy = False

        # 历史记录
        self._history = HistoryManager()

        # 鼠标监听器（用于检测点击窗口外部）
        self._mouse_listener: pynput_mouse.Listener | None = None

        # 通知音效（两个独立播放器，互不干扰）
        self._start_player = QMediaPlayer(self)
        self._start_audio_out = QAudioOutput(self)
        self._start_player.setAudioOutput(self._start_audio_out)
        self._start_player.setSource(
            QUrl.fromLocalFile(str(_SOUND_START))
        )

        self._end_player = QMediaPlayer(self)
        self._end_audio_out = QAudioOutput(self)
        self._end_player.setAudioOutput(self._end_audio_out)
        self._end_player.setSource(
            QUrl.fromLocalFile(str(_SOUND_END))
        )

        # ── 信号连接 ──
        self._hotkey.pressed.connect(self._on_key_pressed)
        self._hotkey.released.connect(self._on_key_released)
        self._hotkey.dismiss.connect(self._on_keyboard_dismiss)
        self._mouse_dismiss_requested.connect(self._on_mouse_dismiss)
        self._window.translate_clicked.connect(self._on_translate)
        self._window.window_closed.connect(self._on_window_closed)
        self._audio.error_occurred.connect(self._on_audio_error)

    # ── 启停 ─────────────────────────────────────────────────
    def start(self):
        self._hotkey.start()

    def stop(self):
        self._hotkey.stop()
        self._audio.stop()
        self._stop_dismiss_mode()
        self._cleanup_workers()

    def update_hotkey(self):
        self._hotkey.update_hotkey(self._config.get("hotkey", "alt_r"))

    # ═══════════════════════════════════════════════════════════
    #  交互关闭：点击外部 / 任意键
    # ═══════════════════════════════════════════════════════════
    def _start_dismiss_mode(self):
        """进入 dismiss 模式：任意键或点击窗口外部关闭窗口。"""
        self._hotkey.set_dismiss_mode(True)
        if self._mouse_listener is None:
            self._mouse_listener = pynput_mouse.Listener(
                on_click=self._on_mouse_click
            )
            self._mouse_listener.daemon = True
            self._mouse_listener.start()

    def _stop_dismiss_mode(self):
        self._hotkey.set_dismiss_mode(False)
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None

    def _on_mouse_click(self, x, y, button, pressed):
        """pynput 鼠标回调（在后台线程）：点击窗口外部时通过 Signal 关闭。

        geometry() 外扩 10px 容差，兼容不同 DPI 缩放下坐标轻微偏差。
        """
        if not pressed:
            return
        if not self._window.isVisible():
            return
        try:
            geo: QRect = self._window.geometry()
            expanded = geo.adjusted(-10, -10, 10, 10)
            if not expanded.contains(QPoint(int(x), int(y))):
                self._mouse_dismiss_requested.emit()
        except Exception:
            pass

    @Slot()
    def _on_keyboard_dismiss(self):
        """任意非热键按键被按下 → 即时关闭窗口。"""
        if self._window.isVisible() and self._state_allows_dismiss():
            self._dismiss_window()

    @Slot()
    def _on_mouse_dismiss(self):
        """鼠标点击窗口外部 → 延迟关闭，避免吞掉翻译按钮等窗口内点击。

        pynput 钩子在 Windows 底层先于 Qt 处理鼠标事件，
        若立即 dismiss，翻译按钮的 clicked 信号还没来得及触发。
        延迟 120ms 让 Qt 先处理完按钮事件，再检查状态决定是否关闭。
        """
        QTimer.singleShot(120, self._check_mouse_dismiss)

    def _check_mouse_dismiss(self):
        if self._window.isVisible() and self._state_allows_dismiss():
            self._dismiss_window()

    def _dismiss_window(self):
        """关闭窗口并清理 dismiss 状态。"""
        self._stop_dismiss_mode()
        if self._window.isVisible():
            self._window.close()

    def _state_allows_dismiss(self) -> bool:
        return self._window.state in (
            FloatingWindow.STATE_DONE,
            FloatingWindow.STATE_ERROR,
        )

    # ═══════════════════════════════════════════════════════════
    #  阶段 1: 按下热键 → 开始录音
    # ═══════════════════════════════════════════════════════════
    @Slot()
    def _on_key_pressed(self):
        # 如果窗口处于完成/错误状态，允许重新开始
        if self._busy:
            if self._state_allows_dismiss():
                self._stop_dismiss_mode()
                self._window.close()
                self._busy = False
            else:
                return
        self._busy = True
        self._stop_dismiss_mode()
        self._cleanup_workers()

        # 重置
        self._asr_buffer = ""
        self._raw_asr_text = ""
        self._optimized_text = ""

        # 播放开始提示音
        self._start_player.setPosition(0)
        self._start_player.play()

        # 显示窗口
        self._window.clear_blocks()
        self._window.set_state(FloatingWindow.STATE_LISTENING)
        self._window.show_at_bottom_center()

        # 开始录音
        self._audio.start()

    # ═══════════════════════════════════════════════════════════
    #  阶段 2: 释放热键 → 停止录音 → ASR 流式识别
    # ═══════════════════════════════════════════════════════════
    @Slot()
    def _on_key_released(self):
        if not self._busy:
            return

        self._audio.stop()

        # 播放结束提示音
        self._end_player.setPosition(0)
        self._end_player.play()

        if self._audio.get_duration() < 0.3:
            self._reset_and_close()
            return

        audio_b64 = self._audio.get_audio_base64()
        if not audio_b64:
            self._reset_and_close()
            return

        self._window.set_state(FloatingWindow.STATE_RECOGNIZING)
        self._window.add_block("asr")

        self._asr_worker = ASRWorker(
            base_url=self._config.get("asr.base_url"),
            model=self._config.get("asr.model"),
            api_key=self._config.get("asr.api_key"),
            audio_base64=audio_b64,
            parent=self,
        )
        self._asr_worker.chunk_received.connect(self._on_asr_chunk)
        self._asr_worker.finished_text.connect(self._on_asr_done)
        self._asr_worker.error.connect(self._on_asr_error)
        self._asr_worker.start()

    @Slot(str)
    def _on_asr_chunk(self, text: str):
        self._asr_buffer += text
        cleaned = clean_asr_output(self._asr_buffer)
        self._window.set_block_text("asr", cleaned)

    @Slot(str)
    def _on_asr_done(self, cleaned_text: str):
        self._raw_asr_text = cleaned_text
        self._window.set_block_text("asr", cleaned_text)

        llm_key = self._config.get("llm.api_key", "")
        if not llm_key:
            # 无 LLM，原文直接作为优化结果保存
            self._history.add_record(cleaned_text, cleaned_text)
            self._finish_with_paste(cleaned_text, "optimize")
            return

        QTimer.singleShot(300, self._start_optimization)

    @Slot(str)
    def _on_asr_error(self, err: str):
        self._window.set_block_text("asr", f"识别失败: {err}")
        self._window.set_state(FloatingWindow.STATE_ERROR)
        self._start_dismiss_mode()
        self._busy = False

    # ═══════════════════════════════════════════════════════════
    #  阶段 3: LLM 文字优化
    # ═══════════════════════════════════════════════════════════
    def _build_optimize_prompt(self) -> str:
        """构建优化 prompt，注入最近 N 条历史记录作为上下文。"""
        ctx_count = self._config.get("history.context_count", 5)
        recent = self._history.get_recent(ctx_count)
        if recent:
            lines = []
            for r in recent:
                lines.append(f"[{r['time']}] {r.get('optimized_text', '')}")
            history_text = "\n".join(lines)
            return OPTIMIZE_PROMPT_WITH_HISTORY.format(
                history=history_text, text=self._raw_asr_text,
            )
        return OPTIMIZE_PROMPT.format(text=self._raw_asr_text)

    def _start_optimization(self):
        self._window.set_state(FloatingWindow.STATE_OPTIMIZING)
        self._window.add_block("optimize")

        prompt = self._build_optimize_prompt()
        self._llm_worker = LLMWorker(
            base_url=self._config.get("llm.base_url"),
            model=self._config.get("llm.model"),
            api_key=self._config.get("llm.api_key"),
            prompt=prompt,
            parent=self,
        )
        self._llm_worker.chunk_received.connect(self._on_optimize_chunk)
        self._llm_worker.finished_text.connect(self._on_optimize_done)
        self._llm_worker.error.connect(self._on_optimize_error)
        self._llm_worker.start()

    @Slot(str)
    def _on_optimize_chunk(self, text: str):
        self._window.append_to_block("optimize", text)

    @Slot(str)
    def _on_optimize_done(self, full_text: str):
        self._optimized_text = full_text
        # 保存到历史记录
        self._history.add_record(self._raw_asr_text, full_text)
        self._finish_with_paste(full_text, "optimize")

    @Slot(str)
    def _on_optimize_error(self, err: str):
        self._window.set_block_text("optimize", f"优化失败: {err}")
        self._window.set_status_text("优化失败，已使用原文")
        self._finish_with_paste(self._raw_asr_text, "optimize")

    # ═══════════════════════════════════════════════════════════
    #  阶段 4: 翻译
    # ═══════════════════════════════════════════════════════════
    @Slot()
    def _on_translate(self):
        self._stop_dismiss_mode()

        llm_key = self._config.get("llm.api_key", "")
        if not llm_key:
            self._window.set_status_text("请先在设置中配置大模型 API Key")
            return

        text = self._optimized_text or self._raw_asr_text
        if not text:
            return

        target = self._config.get("translation.target_language", "English")
        prompt = TRANSLATE_PROMPT.format(target_language=target, text=text)

        self._window.set_state(FloatingWindow.STATE_TRANSLATING)
        self._window.add_block("translate")

        self._llm_worker = LLMWorker(
            base_url=self._config.get("llm.base_url"),
            model=self._config.get("llm.model"),
            api_key=self._config.get("llm.api_key"),
            prompt=prompt,
            parent=self,
        )
        self._llm_worker.chunk_received.connect(self._on_translate_chunk)
        self._llm_worker.finished_text.connect(self._on_translate_done)
        self._llm_worker.error.connect(self._on_translate_error)
        self._llm_worker.start()

    @Slot(str)
    def _on_translate_chunk(self, text: str):
        self._window.append_to_block("translate", text)

    @Slot(str)
    def _on_translate_done(self, full_text: str):
        self._copy_to_clipboard(full_text)
        # 给最近的历史记录补充翻译
        self._history.update_last_translation(full_text)
        self._window.mark_translated()
        self._window.set_state(FloatingWindow.STATE_DONE)
        self._window.set_status_text("翻译完成")
        self._window.show_block_copied("translate")
        self._start_dismiss_mode()

    @Slot(str)
    def _on_translate_error(self, err: str):
        self._window.set_block_text("translate", f"翻译失败: {err}")
        self._window.set_state(FloatingWindow.STATE_ERROR)
        self._start_dismiss_mode()

    # ═══════════════════════════════════════════════════════════
    #  辅助方法
    # ═══════════════════════════════════════════════════════════
    def _finish_with_paste(self, text: str, copied_block: str):
        """完成流程：复制 → 块内"已复制"提示 → 自动粘贴 → 启用 dismiss。

        注意：dismiss 模式必须在 auto_paste 之后才能启用，否则
        模拟的 Ctrl+V 按键会被 pynput 监听到，立刻触发 dismiss 关闭窗口。
        """
        self._copy_to_clipboard(text)
        self._window.set_state(FloatingWindow.STATE_DONE)
        self._window.show_block_copied(copied_block)
        # 先粘贴，粘贴完成后再启用 dismiss
        QTimer.singleShot(200, self._auto_paste)

    def _copy_to_clipboard(self, text: str):
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

    def _auto_paste(self):
        """模拟 Ctrl+V 粘贴到当前焦点输入框，完成后启用 dismiss 模式。"""
        if not self._window.isActiveWindow():
            try:
                kb = KbController()
                kb.press(PynputKey.ctrl_l)
                kb.press('v')
                kb.release('v')
                kb.release(PynputKey.ctrl_l)
            except Exception:
                pass
        # 等待模拟按键事件传播完毕后，再启用 dismiss（避免被自己的按键触发）
        QTimer.singleShot(300, self._start_dismiss_mode)

    def _reset_and_close(self):
        self._busy = False
        self._window.close()

    @Slot()
    def _on_window_closed(self):
        self._stop_dismiss_mode()
        self._busy = False
        self._cleanup_workers()

    @Slot(str)
    def _on_audio_error(self, err: str):
        self._window.set_status_text(f"麦克风错误: {err}")
        self._window.set_state(FloatingWindow.STATE_ERROR)
        self._start_dismiss_mode()
        self._busy = False

    def _cleanup_workers(self):
        for worker in (self._asr_worker, self._llm_worker):
            if worker is not None and worker.isRunning():
                worker.quit()
                worker.wait(2000)
