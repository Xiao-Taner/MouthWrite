# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置文件。

使用方法：
    pip install pyinstaller
    pyinstaller MouthWrite.spec

生成的 .exe 位于 dist/ 目录下。
"""

import os
import glob
import shutil
import sounddevice as sd

# 获取 sounddevice 的 PortAudio 动态库路径
def get_portaudio_dll():
    """获取 sounddevice 依赖的 PortAudio DLL 路径。"""
    try:
        # sounddevice.query_devices 会加载 PortAudio，找不到会抛异常
        sd.query_devices()
    except Exception:
        pass
    # 尝试从 site-packages 中找到
    import site
    for p in site.getsitepackages():
        for pattern in ["**/portaudio*.dll", "**/_sounddevice*.pyd"]:
            for f in glob.glob(os.path.join(p, pattern), recursive=True):
                return os.path.dirname(f)
    return None

pa_dir = get_portaudio_dll()

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[
        # sounddevice 依赖的 PortAudio DLL
        (pa_dir, ".") if pa_dir else (".", "."),
    ] if pa_dir else [],
    datas=[
        # 音效资源文件
        ("gui/start.mp3", "gui"),
        ("gui/end.mp3", "gui"),
    ],
    hiddenimports=[
        # pynput 平台后端（Windows）
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        # sounddevice 相关
        "sounddevice",
        "_sounddevice_data",
        "numpy",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的模块以减小体积
        "tkinter",
        "unittest",
        "test",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MouthWrite",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # False = 无控制台窗口（GUI 应用）
    # 调试时可改为 True 查看控制台输出
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # 如果有 .ico 图标文件，可在此指定
    icon="assets/icon.ico",
)
