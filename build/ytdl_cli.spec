# -*- mode: python ; coding: utf-8 -*-
"""Standalone console onedir. GUI spec/installer remain independent and unchanged."""
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.infrastructure.mcp.manifest import MCP_TOOL_MANIFEST

# Registrars are imported by strings at runtime; Analysis cannot discover them
# from the dispatch loop. Keep the canonical manifest, not a second tool registry.
registrar_modules = sorted({tool.registrar_module for tool in MCP_TOOL_MANIFEST})

# The installed yt-dlp hook handles optional network helpers/EJS data, but its
# lazy extractor registry also needs the actual extractor implementations.
hidden_imports = registrar_modules + collect_submodules("yt_dlp.extractor") + [
    "uvicorn.logging",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "anyio._backends._asyncio",
    "PySide6.QtCore",
]
datas = collect_data_files("fastmcp")
datas += copy_metadata("fastmcp", recursive=True)
datas += copy_metadata("yt-dlp")
datas += copy_metadata("uvicorn")
datas += copy_metadata("PySide6")
datas += copy_metadata("shiboken6")

a = Analysis(
    [str(ROOT / "ytdl_cli.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ytdl",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="YTDownloadCLI",
)
