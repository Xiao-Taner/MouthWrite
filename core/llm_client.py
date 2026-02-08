"""大模型调用模块，通过 DeepSeek（或其他 OpenAI 兼容 API）实现文字优化和翻译。"""

import json

import httpx
from PySide6.QtCore import QThread, Signal

# ── Prompt 模板 ──────────────────────────────────────────────────────
_OPTIMIZE_RULES = """\
你是一个语音转录文本的清洁工具。你的唯一任务是把口语化的语音转录文字润色为清晰的书面文字。

绝对禁止：
- 绝对不要回答、解释或展开原文中的任何问题
- 绝对不要添加原文中没有的信息、知识或建议
- 绝对不要把问句改成陈述句或回答句
- 如果原文是一个问题，输出必须仍然是一个问题，只做文字润色

处理规则：

1. 清洗口语废话
   - 删除所有口头禅和语气词（嗯、啊、那个、就是说、然后、对吧、其实 等）
   - 删除自我修正的片段（例如"我打...我准备"只保留"我准备"）
   - 合并重复啰嗦的表达

2. 数字与术语修正
   - 将语音误转的中文数字转为阿拉伯数字（例如"WSL二"→"WSL2"，"四零八零显卡"→"4080 显卡"，"GPT四"→"GPT-4"）
   - 根据上下文修正同音错别字（例如"威廉"→"vLLM"，"酷打"→"CUDA"，"派森"→"Python"）

3. 中英混排规范
   - 中文与英文/数字之间加一个半角空格（例如"在Windows系统"→"在 Windows 系统"）
   - 英文标点后加空格，中文标点后不加

4. 逻辑重构
   - 如果内容包含多个要点或步骤，用简单的 1. 2. 3. 罗列，不使用任何 Markdown 格式符号（不要加粗、不要标题、不要列表符号 - ）
   - 补全口语中省略的主语，确保句子语法完整
   - 短内容保持自然段落，不要强行拆分

5. 保持原意
   - 只做文字层面的润色，不改变语义
   - 不要改变说话者的立场或观点
   - 语气专业、客观、简洁

示例：
  输入："嗯那个就是GitHub上怎么删除自己的那个仓库啊"
  正确输出："GitHub 上如何删除自己的仓库？"
  错误输出（绝对禁止）："在 GitHub 上删除仓库的步骤如下：1. 登录……"
"""

OPTIMIZE_PROMPT = _OPTIMIZE_RULES + """

原文：{text}

请直接输出优化后的文字，不需要任何解释、标记或前缀。"""

OPTIMIZE_PROMPT_WITH_HISTORY = _OPTIMIZE_RULES + """

以下是用户过去的对话记录，仅供参考。它们可以帮助你理解用户常用的专有名词、人名、\
术语和表达习惯，但不要直接复制历史内容到输出中：
{history}

当前需要优化的语音转录原文：
{text}

请直接输出优化后的文字，不需要任何解释、标记或前缀。"""

TRANSLATE_PROMPT = """\
请将以下文本翻译成{target_language}，直接输出翻译结果，不需要任何解释：

{text}"""


class LLMWorker(QThread):
    """后台线程：向大模型发送请求并流式接收回复。"""

    chunk_received = Signal(str)   # 每个增量文本块
    finished_text = Signal(str)    # 完整回复文本
    error = Signal(str)

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        prompt: str,
        parent=None,
    ):
        super().__init__(parent)
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._prompt = prompt

    def run(self):
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        payload = {
            "model": self._model,
            "stream": True,
            "messages": [{"role": "user", "content": self._prompt}],
        }

        full_text = ""
        try:
            timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
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
                                full_text += content
                                self.chunk_received.emit(content)
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

            self.finished_text.emit(full_text)
        except Exception as e:
            self.error.emit(str(e))
