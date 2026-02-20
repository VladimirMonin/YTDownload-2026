"""Скрипт загрузки FFmpeg для Windows (x64).

Скачивает FFmpeg из официального источника (gyan.dev builds — статическая сборка LGPL)
и распаковывает бинарники в vendor/ffmpeg/bin/.

Запуск:
    uv run python scripts/download_ffmpeg.py
    # или
    python scripts/download_ffmpeg.py

Переменные окружения:
    FFMPEG_VERSION  — конкретная версия (по умолчанию: latest-release)
    FFMPEG_URL      — прямая ссылка на ZIP (переопределяет автоопределение)
"""

from __future__ import annotations

import hashlib
import os
import shutil
import struct
import sys
import urllib.request
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

# Официальные gyan.dev сборки FFmpeg — LGPL essential (без GPL-компонентов)
# Страница: https://www.gyan.dev/ffmpeg/builds/
FFMPEG_RELEASE_URL = (
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
)
# Контрольная сумма на той же странице (файл .sha256)
FFMPEG_SHA256_URL = (
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256"
)

ROOT = Path(__file__).parent.parent
VENDOR_BIN = ROOT / "vendor" / "ffmpeg" / "bin"
DOWNLOAD_CACHE = ROOT / "vendor" / "ffmpeg" / "_download_cache"

BINARIES = ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe")


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def _progress_hook(block_num: int, block_size: int, total_size: int) -> None:
    """Callback для urllib.request.urlretrieve — показывает прогресс."""
    if total_size <= 0:
        print(f"\r  Скачано: {block_num * block_size // 1024 // 1024} MB ...", end="", flush=True)
        return
    downloaded = block_num * block_size
    pct = min(int(downloaded * 100 / total_size), 100)
    mb_done = downloaded // 1024 // 1024
    mb_total = total_size // 1024 // 1024
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    print(f"\r  [{bar}] {pct:3d}% — {mb_done}/{mb_total} MB", end="", flush=True)


def _sha256_file(path: Path) -> str:
    """Вычисляет SHA-256 файла."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch_text(url: str) -> str:
    """Скачивает текстовый файл по URL."""
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
        return resp.read().decode("utf-8").strip()


# ---------------------------------------------------------------------------
# Основные шаги
# ---------------------------------------------------------------------------

def download_zip(url: str, dest: Path) -> Path:
    """Скачивает ZIP-архив FFmpeg в кэш."""
    zip_path = dest / "ffmpeg.zip"
    if zip_path.exists():
        print(f"  Архив уже в кэше: {zip_path}")
        return zip_path

    dest.mkdir(parents=True, exist_ok=True)
    print(f"\nСкачиваю FFmpeg\n  URL: {url}")
    try:
        urllib.request.urlretrieve(url, zip_path, _progress_hook)  # noqa: S310
        print()  # новая строка после прогресс-бара
    except Exception as e:
        zip_path.unlink(missing_ok=True)
        raise RuntimeError(f"Ошибка загрузки: {e}") from e

    return zip_path


def verify_checksum(zip_path: Path, sha256_url: str) -> None:
    """Проверяет SHA-256 скачанного архива."""
    print("\nПроверяю контрольную сумму ...")
    try:
        expected = _fetch_text(sha256_url).lower().split()[0]
    except Exception as e:
        print(f"  ПРЕДУПРЕЖДЕНИЕ: не удалось получить SHA-256 ({e}). Пропускаю проверку.")
        return

    actual = _sha256_file(zip_path).lower()
    if actual != expected:
        zip_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Контрольная сумма не совпадает!\n  ожидалось: {expected}\n  получено:  {actual}"
        )
    print("  ✓ SHA-256 совпадает")


def extract_binaries(zip_path: Path, dest_bin: Path) -> None:
    """Извлекает ffmpeg.exe / ffprobe.exe / ffplay.exe из архива."""
    print(f"\nИзвлекаю бинарники → {dest_bin}")
    dest_bin.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        all_names = zf.namelist()
        for binary in BINARIES:
            # Ищем в bin/ внутри архива (путь вида ffmpeg-N.N-essentials_build/bin/ffmpeg.exe)
            candidates = [n for n in all_names if n.endswith(f"/bin/{binary}")]
            if not candidates:
                print(f"  ✗ {binary} — не найден в архиве!")
                continue

            member = candidates[0]
            with zf.open(member) as src, open(dest_bin / binary, "wb") as dst:
                shutil.copyfileobj(src, dst)

            size_mb = (dest_bin / binary).stat().st_size / 1024 / 1024
            print(f"  ✓ {binary} ({size_mb:.1f} MB)")


def check_existing() -> bool:
    """Проверяет, все ли бинарники уже присутствуют."""
    return all((VENDOR_BIN / b).exists() for b in BINARIES)


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def main() -> None:
    """Точка входа."""
    print("=" * 55)
    print("  FFmpeg Downloader для YT Downloader 2026")
    print("=" * 55)

    if check_existing():
        print(f"\n✓ FFmpeg уже установлен: {VENDOR_BIN}")
        for b in BINARIES:
            size_mb = (VENDOR_BIN / b).stat().st_size / 1024 / 1024
            print(f"  {b} ({size_mb:.1f} MB)")
        answer = input("\nПереустановить? [y/N]: ").strip().lower()
        if answer != "y":
            print("Выход.")
            return

    url = os.getenv("FFMPEG_URL", FFMPEG_RELEASE_URL)
    sha_url = FFMPEG_SHA256_URL

    zip_path = download_zip(url, DOWNLOAD_CACHE)
    verify_checksum(zip_path, sha_url)
    extract_binaries(zip_path, VENDOR_BIN)

    # Очистка кэша
    shutil.rmtree(DOWNLOAD_CACHE, ignore_errors=True)

    print(f"\n✅ FFmpeg готов: {VENDOR_BIN}")
    print("   Теперь можно запустить: uv run python app.py")


if __name__ == "__main__":
    main()
