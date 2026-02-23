"""全局热键监听模块，基于 pynput 实现 RAlt 等按键的长按检测。

新增 dismiss 模式：启用后，任意非热键按键触发 dismiss 信号（用于关闭浮动窗口）。
"""

from pynput import keyboard
from PySide6.QtCore import QObject, Signal


class HotkeyListener(QObject):
    """在后台线程中监听全局热键的按下/释放事件，并通过 Qt 信号通知主线程。"""

    pressed = Signal()
    released = Signal()
    dismiss = Signal()  # dismiss 模式下，任意非热键按键触发

    # 可选的热键映射表
    # 注意：Windows 上右 Alt 可能被报告为 alt_r 或 alt_gr，需要同时匹配
    HOTKEY_MAP: dict[str, tuple[keyboard.Key, ...]] = {
        "alt_r": (keyboard.Key.alt_r, keyboard.Key.alt_gr),
        "alt_gr": (keyboard.Key.alt_r, keyboard.Key.alt_gr),
        "alt_l": (keyboard.Key.alt_l,),
        "ctrl_r": (keyboard.Key.ctrl_r,),
        "ctrl_l": (keyboard.Key.ctrl_l,),
        "shift_r": (keyboard.Key.shift_r,),
        "shift_l": (keyboard.Key.shift_l,),
        "f1": (keyboard.Key.f1,),
        "f2": (keyboard.Key.f2,),
        "f3": (keyboard.Key.f3,),
        "f4": (keyboard.Key.f4,),
        "f5": (keyboard.Key.f5,),
        "f6": (keyboard.Key.f6,),
        "f7": (keyboard.Key.f7,),
        "f8": (keyboard.Key.f8,),
        "f9": (keyboard.Key.f9,),
        "f10": (keyboard.Key.f10,),
        "f11": (keyboard.Key.f11,),
        "f12": (keyboard.Key.f12,),
    }

    def __init__(
        self,
        hotkey_name: str = "alt_r",
        translate_modifier_name: str = "ctrl_r",
        parent=None,
    ):
        super().__init__(parent)
        self._target_keys = self.HOTKEY_MAP.get(
            hotkey_name, (keyboard.Key.alt_r, keyboard.Key.alt_gr)
        )
        self._translate_modifier_keys = self.HOTKEY_MAP.get(
            translate_modifier_name, (keyboard.Key.ctrl_r,)
        )
        self._is_pressed = False
        self._translate_combo_active = False
        self._translate_requested_last_session = False
        self._pressed_keys: set = set()
        self._dismiss_mode = False
        self._listener: keyboard.Listener | None = None

    # ------------------------------------------------------------------
    def start(self):
        if self._listener is not None:
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()
        print(f"[MouthWrite] 热键监听已启动，目标键: {self._target_keys}")

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    # ------------------------------------------------------------------
    def update_hotkey(self, hotkey_name: str, translate_modifier_name: str = "ctrl_r"):
        self._target_keys = self.HOTKEY_MAP.get(
            hotkey_name, (keyboard.Key.alt_r, keyboard.Key.alt_gr)
        )
        self._translate_modifier_keys = self.HOTKEY_MAP.get(
            translate_modifier_name, (keyboard.Key.ctrl_r,)
        )
        self._is_pressed = False
        self._translate_combo_active = False
        self._pressed_keys.clear()

    def consume_translate_request(self) -> bool:
        """读取并清空最近一次会话是否请求翻译。"""
        value = self._translate_requested_last_session
        self._translate_requested_last_session = False
        return value

    def set_dismiss_mode(self, enabled: bool):
        """启用/禁用 dismiss 模式。启用后任意非热键按键触发 dismiss 信号。"""
        self._dismiss_mode = enabled

    # ------------------------------------------------------------------
    def _on_press(self, key):
        self._pressed_keys.add(key)
        # 热键优先
        if key in self._target_keys:
            if not self._is_pressed:
                self._is_pressed = True
                # 按下主热键瞬间就检测一次组合键状态（支持先按修饰键再按主热键）
                self._translate_combo_active = any(
                    k in self._pressed_keys for k in self._translate_modifier_keys
                )
                self.pressed.emit()
            return

        # 主热键按住期间，如果按下翻译修饰键，则本轮会话标记为“需要翻译”
        if self._is_pressed and key in self._translate_modifier_keys:
            self._translate_combo_active = True
            return

        # dismiss 模式：任意其他键 → 关闭窗口
        if self._dismiss_mode:
            self.dismiss.emit()

    def _on_release(self, key):
        if key in self._pressed_keys:
            self._pressed_keys.remove(key)
        if key in self._target_keys and self._is_pressed:
            self._is_pressed = False
            self._translate_requested_last_session = self._translate_combo_active
            self._translate_combo_active = False
            self.released.emit()
