"""Скрипт сборки YT Downloader.

Запуск:
    uv run python build/build.py

Pipeline:
    1. PyInstaller (onedir) → dist/YTDownloader/_internal/ + YTDownloader.exe
    2. Копирование FFmpeg ВНЕ _internal → dist/YTDownloader/vendor/ffmpeg/bin/
    3. Копирование лицензий → dist/YTDownloader/licenses/

LGPL Compliance:
    - onedir: DLL PySide6 лежат в _internal/PySide6/ (заменяемы)
    - FFmpeg: лежат в vendor/ffmpeg/bin/ рядом с .exe (заменяемы)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent          # c:\PY\youtube_downloader
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist" / "YTDownloader"
SPEC_FILE = BUILD_DIR / "ytdownloader.spec"


def run_pyinstaller() -> None:
    """Запускает PyInstaller с .spec файлом."""
    print("\n=== PyInstaller (onedir) ===")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(SPEC_FILE), "--noconfirm"],
        cwd=ROOT,
        check=True,
    )
    print(f"PyInstaller завершён: exit={result.returncode}")


def copy_ffmpeg_outside_internal() -> None:
    """Копирует FFmpeg ВНЕ _internal — требование LGPL (библиотеки должны быть заменяемы).

    Итоговое расположение:
        dist/YTDownloader/vendor/ffmpeg/bin/ffmpeg.exe
        dist/YTDownloader/vendor/ffmpeg/bin/ffprobe.exe
        dist/YTDownloader/vendor/ffmpeg/bin/ffplay.exe
    """
    print("\n=== FFmpeg → vendor/ffmpeg/bin/ (вне _internal) ===")

    src_bin = ROOT / "vendor" / "ffmpeg" / "bin"
    dst_bin = DIST_DIR / "vendor" / "ffmpeg" / "bin"
    dst_bin.mkdir(parents=True, exist_ok=True)

    copied = 0
    for fname in ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe"):
        src = src_bin / fname
        if src.exists():
            shutil.copy2(src, dst_bin / fname)
            print(f"  ✓ {fname}")
            copied += 1
        else:
            print(f"  ✗ {fname} — не найден в {src_bin}")

    if copied == 0:
        print("  ПРЕДУПРЕЖДЕНИЕ: FFmpeg не скопирован!")
    else:
        print(f"  Скопировано {copied} файлов → {dst_bin}")


def copy_licenses() -> None:
    """Копирует лицензии в dist/YTDownloader/licenses/."""
    print("\n=== Лицензии → licenses/ ===")

    dst_licenses = DIST_DIR / "licenses"
    dst_licenses.mkdir(parents=True, exist_ok=True)

    entries = [
        (ROOT / "vendor" / "ffmpeg" / "LICENSE.txt",      "FFmpeg_LICENSE.txt"),
        (ROOT / "resources" / "fonts" / "OFL.txt",         "Fonts_OFL.txt"),
        (ROOT / "resources" / "icons" / "tabler" / "LICENSE", "TablerIcons_LICENSE.txt"),
    ]

    for src, dst_name in entries:
        dst = dst_licenses / dst_name
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  ✓ {dst_name}")
        else:
            print(f"  ✗ {dst_name} — {src} не найден")

    # THIRD_PARTY_NOTICES.txt (если есть)
    notices = ROOT / "THIRD_PARTY_NOTICES.txt"
    if notices.exists():
        shutil.copy2(notices, DIST_DIR / "THIRD_PARTY_NOTICES.txt")
        print("  ✓ THIRD_PARTY_NOTICES.txt")


def print_summary() -> None:
    """Выводит итоговую структуру dist/."""
    print("\n=== Структура dist/YTDownloader/ ===")
    if not DIST_DIR.exists():
        print("  [dist не найден]")
        return

    for path in sorted(DIST_DIR.rglob("*")):
        rel = path.relative_to(DIST_DIR)
        depth = len(rel.parts) - 1
        indent = "  " + "│   " * depth + ("├── " if depth > 0 else "")
        name = path.name + ("/" if path.is_dir() else "")
        # Печатаем только первые 3 уровня вложенности для краткости
        if len(rel.parts) <= 3:
            print(f"  {indent}{name}")

    # Ключевые файлы
    exe = DIST_DIR / "YTDownloader.exe"
    ffmpeg = DIST_DIR / "vendor" / "ffmpeg" / "bin" / "ffmpeg.exe"
    internal = DIST_DIR / "_internal"
    print(f"\n  EXE:     {'✓' if exe.exists() else '✗'} {exe.name}")
    print(f"  FFmpeg:  {'✓' if ffmpeg.exists() else '✗'} vendor/ffmpeg/bin/ffmpeg.exe")
    print(f"  _internal: {'✓' if internal.exists() else '✗'} {internal.name}/")


def main() -> None:
    """Точка входа скрипта сборки."""
    print(f"ROOT: {ROOT}")
    print(f"DIST: {DIST_DIR}")

    run_pyinstaller()
    copy_ffmpeg_outside_internal()
    copy_licenses()
    print_summary()
    print("\n✅ Сборка завершена!")


if __name__ == "__main__":
    main()
