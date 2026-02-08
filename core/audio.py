"""音频采集模块，使用 sounddevice 通过回调式低延迟录音。"""

import io
import wave
import base64

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, Signal


class AudioRecorder(QObject):
    """录音器：start() 开始录音，stop() 结束录音，然后通过 get_audio_base64() 获取结果。"""

    error_occurred = Signal(str)

    def __init__(self, sample_rate: int = 16000, channels: int = 1, parent=None):
        super().__init__(parent)
        self._sample_rate = sample_rate
        self._channels = channels
        self._frames: list[np.ndarray] = []
        self._recording = False
        self._stream: sd.InputStream | None = None

    # ------------------------------------------------------------------
    def start(self):
        self._frames.clear()
        self._recording = True
        try:
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="int16",
                blocksize=1024,
                callback=self._callback,
            )
            self._stream.start()
        except Exception as e:
            self._recording = False
            self.error_occurred.emit(f"无法启动麦克风: {e}")

    def stop(self):
        self._recording = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    # ------------------------------------------------------------------
    def _callback(self, indata: np.ndarray, frames: int, time_info, status):
        if status:
            self.error_occurred.emit(str(status))
        if self._recording:
            self._frames.append(indata.copy())

    # ------------------------------------------------------------------
    def get_audio_base64(self) -> str:
        """将录制的音频编码为 WAV 格式的 Base64 字符串。"""
        if not self._frames:
            return ""

        audio_data = np.concatenate(self._frames, axis=0)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self._channels)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(self._sample_rate)
            wf.writeframes(audio_data.tobytes())

        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def get_duration(self) -> float:
        """获取录制时长（秒）。"""
        if not self._frames:
            return 0.0
        total_samples = sum(f.shape[0] for f in self._frames)
        return total_samples / self._sample_rate
