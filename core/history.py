"""历史记录管理模块 —— 本地 JSON 持久化每次转录/优化/翻译结果。"""

import json
import os
from datetime import datetime
from pathlib import Path


class HistoryManager:
    """管理转录历史记录，存储在 %APPDATA%/MouthWrite/history.json。

    每条记录格式::

        {
            "time": "2026-02-07 14:30:00",
            "asr_text": "原始转录文本",
            "optimized_text": "优化后文本",
            "translated_text": ""          # 可选
        }

    记录按时间倒序排列（最新在前）。
    """

    _MAX_RECORDS = 500

    def __init__(self):
        self._path = self._get_path()
        self._records: list[dict] = []
        self._load()

    @staticmethod
    def _get_path() -> Path:
        app_dir = Path(os.environ.get("APPDATA", ".")) / "MouthWrite"
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir / "history.json"

    # ── 加载 / 保存 ──────────────────────────────────────
    def _load(self):
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._records = data
            except (json.JSONDecodeError, OSError):
                self._records = []

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._records, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    # ── 公共接口 ──────────────────────────────────────────
    def add_record(
        self,
        asr_text: str,
        optimized_text: str,
        translated_text: str = "",
    ):
        """添加一条记录（时间自动生成），最新在前。"""
        record: dict = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "asr_text": asr_text,
            "optimized_text": optimized_text,
        }
        if translated_text:
            record["translated_text"] = translated_text
        self._records.insert(0, record)
        if len(self._records) > self._MAX_RECORDS:
            self._records = self._records[: self._MAX_RECORDS]
        self._save()

    def update_last_translation(self, translated_text: str):
        """给最近一条记录补充翻译结果。"""
        if self._records:
            self._records[0]["translated_text"] = translated_text
            self._save()

    def get_recent(self, n: int) -> list[dict]:
        return self._records[:n]

    def get_all(self) -> list[dict]:
        return self._records.copy()

    def clear(self):
        self._records.clear()
        self._save()

    def reload(self):
        self._load()
