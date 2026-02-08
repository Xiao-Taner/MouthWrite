"""ASR 流式调用模块，通过 httpx 与 OpenAI 兼容 API 通信。

支持两种 API 格式（根据 base_url 自动检测）：
  · 本地 vLLM —— audio_url 格式
  · DashScope (千问) —— input_audio 格式 + asr_options
"""

import re
import json

import httpx
from PySide6.QtCore import QThread, Signal

# 用于自动识别 DashScope 类 API 的关键词
_DASHSCOPE_KEYWORDS = ("dashscope", "aliyuncs")


def _is_dashscope(base_url: str) -> bool:
    """判断 base_url 是否为 DashScope (阿里云千问) 系列 API。"""
    lower = base_url.lower()
    return any(kw in lower for kw in _DASHSCOPE_KEYWORDS)


def clean_asr_output(text: str) -> str:
    """清理 ASR 模型输出中的语言标签等特殊标记。

    Qwen3-ASR 通过 vLLM 输出的格式可能为 ``<|zh|>文字内容<|endoftext|>``，
    此函数将标签去除，只保留纯文本。
    """
    text = re.sub(r"<\|[^|]*\|>", "", text)
    return text.strip()


class ASRWorker(QThread):
    """后台线程：将音频发送到 ASR 服务并流式接收转录文本。"""

    chunk_received = Signal(str)   # 每个增量文本块
    finished_text = Signal(str)    # 完整文本（已清理）
    error = Signal(str)

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        audio_base64: str,
        parent=None,
    ):
        super().__init__(parent)
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._audio_base64 = audio_base64
        self._dashscope = _is_dashscope(self._base_url)

    def _build_payload(self) -> dict:
        """根据 API 类型构建请求 payload。"""
        data_uri = f"data:audio/wav;base64,{self._audio_base64}"

        if self._dashscope:
            # DashScope (千问) 格式：input_audio + asr_options
            payload = {
                "model": self._model,
                "stream": True,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {"data": data_uri},
                            }
                        ],
                    }
                ],
                "asr_options": {
                    "enable_itn": False,
                },
            }
        else:
            # 本地 vLLM 格式：audio_url
            payload = {
                "model": self._model,
                "stream": True,
                "temperature": 0.0,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "audio_url",
                                "audio_url": {"url": data_uri},
                            }
                        ],
                    }
                ],
            }
        return payload

    def run(self):
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        payload = self._build_payload()

        raw_text = ""
        try:
            timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)
            with httpx.Client(timeout=timeout) as client:
                with client.stream("POST", url, json=payload, headers=headers) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                raw_text += content
                                self.chunk_received.emit(content)
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

            cleaned = clean_asr_output(raw_text)
            self.finished_text.emit(cleaned)
        except Exception as e:
            self.error.emit(str(e))
