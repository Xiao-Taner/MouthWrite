"""持久化配置管理模块，使用 JSON 文件存储所有可配置项。"""

import json
import os
import copy
from pathlib import Path

DEFAULT_CONFIG = {
    "hotkey": "alt_r",
    "hotkey_translate_modifier": "ctrl_r",
    "asr": {
        "base_url": "http://localhost:8000/v1",
        "model": "Qwen/Qwen3-ASR-1.7B",
        "api_key": "EMPTY",
    },
    "llm": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key": "",
    },
    "translation": {
        "target_language": "English",
    },
    "history": {
        "context_count": 5,
    },
    "optimize": {
        "rules": "",
    },
    "startup": {
        "enabled": False,
    },
}


class Config:
    """单例配置管理器，配置文件存储在 %APPDATA%/MouthWrite/config.json。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._data = {}
        self._load()

    # ------------------------------------------------------------------
    @property
    def config_path(self) -> Path:
        app_dir = Path(os.environ.get("APPDATA", ".")) / "MouthWrite"
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir / "config.json"

    # ------------------------------------------------------------------
    def _load(self):
        path = self.config_path
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = copy.deepcopy(DEFAULT_CONFIG)
        else:
            self._data = copy.deepcopy(DEFAULT_CONFIG)
            self.save()

        # 补全缺失的键（版本升级兼容）
        self._merge_defaults(self._data, DEFAULT_CONFIG)
        self.save()

    def _merge_defaults(self, data: dict, defaults: dict):
        for key, default_value in defaults.items():
            if key not in data:
                data[key] = copy.deepcopy(default_value)
            elif isinstance(default_value, dict) and isinstance(data.get(key), dict):
                self._merge_defaults(data[key], default_value)

    # ------------------------------------------------------------------
    def save(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def reload(self):
        self._load()

    # ------------------------------------------------------------------
    def get(self, dotted_key: str, default=None):
        """通过点号分隔的键路径获取值，例如 ``get('asr.base_url')``。"""
        keys = dotted_key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    def set(self, dotted_key: str, value):
        """通过点号分隔的键路径设置值并自动持久化。"""
        keys = dotted_key.split(".")
        d = self._data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value
        self.save()

    @property
    def data(self) -> dict:
        return self._data
