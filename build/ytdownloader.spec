# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — YT Downloader.

Режим: onedir (LGPL compliance — DLL-файлы PySide6 и FFmpeg заменяемы).

Структура dist/YTDownloader/:
    YTDownloader.exe          ← точка входа
    _internal/                ← Python runtime, PySide6, пакеты
        PySide6/              ← LGPL — заменяемые DLL
        resources/fonts/      ← OFL шрифты
        resources/icons/      ← MIT иконки Tabler
    vendor/ffmpeg/bin/        ← LGPL — FFmpeg, копируется build.py ВНЕ _internal
"""

import os
from pathlib import Path

# Корень проекта = папка на уровень выше spec-файла
ROOT = Path(SPECPATH).parent

block_cipher = None

# ---------------------------------------------------------------------------
# Data files, которые едут ВНУТРЬ _internal/
# (fonts, icons — статические ресурсы приложения)
# FFmpeg намеренно НЕ здесь — build.py копирует его ВНЕ _internal.
# ---------------------------------------------------------------------------
datas = [
    (str(ROOT / "resources" / "fonts"),  "resources/fonts"),
    (str(ROOT / "resources" / "icons"),  "resources/icons"),
]

# ---------------------------------------------------------------------------
# Hidden imports — FastMCP / uvicorn динамически импортируют свои модули,
# PyInstaller их не видит при анализе.
# ---------------------------------------------------------------------------
hidden_imports = [
    # uvicorn
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "uvicorn.logging",
    "uvicorn.main",
    # h11 (HTTP/1.1 парсер для uvicorn)
    "h11",
    "h11._connection",
    "h11._events",
    # anyio backends
    "anyio._backends._asyncio",
    # yt-dlp extractors (динамических импортов очень много — greedily)
    "yt_dlp.extractor.youtube",
    "yt_dlp.utils",
    # PySide6 — PyInstaller hook должен подтянуть, но на всякий случай
    "PySide6.QtXml",
    "PySide6.QtNetwork",
    "PySide6.QtSvg",
]

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Тяжёлые пакеты, которых точно нет в проекте
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "PIL",
        "IPython",
        "notebook",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir: бинарники идут в COLLECT, не в exe
    name="YTDownloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # GUI-приложение, без консольного окна
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "resources" / "icons" / "app.ico"),
    version_file=None,
    manifest=str(ROOT / "resources" / "app.manifest"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[
        # PySide6 DLL крашатся при UPX-компрессии
        "Qt6*.dll",
        "PySide6*.pyd",
        "shiboken6*.pyd",
    ],
    name="YTDownloader",
)
