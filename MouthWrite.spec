# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置文件。

使用方法：
    pip install pyinstaller
    pyinstaller MouthWrite.spec

生成的 .exe 位于 dist/ 目录下。
"""

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        # 音效资源文件
        ("gui/start.mp3", "gui"),
        ("gui/end.mp3", "gui"),
    ],
    hiddenimports=[
        # pynput 平台后端（Windows）
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        # sounddevice PortAudio 数据
        "sounddevice",
        "_sounddevice_data",
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
