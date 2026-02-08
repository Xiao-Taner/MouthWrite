"""通用工具函数。"""

import sys
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    """获取资源文件的绝对路径，兼容开发环境和 PyInstaller 打包后的环境。

    - 开发环境：相对于项目根目录（即本文件所在目录）
    - 打包后：相对于 PyInstaller 临时解压目录（sys._MEIPASS）
    """
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后的运行环境
        base_path = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        # 普通 Python 开发环境
        base_path = Path(__file__).resolve().parent
    return base_path / relative_path
