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

import argparse
import hashlib
import importlib.metadata as metadata
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent  # c:\PY\youtube_downloader
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
        (ROOT / "vendor" / "ffmpeg" / "LICENSE.txt", "FFmpeg_LICENSE.txt"),
        (ROOT / "resources" / "fonts" / "OFL.txt", "Fonts_OFL.txt"),
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


def reserve_cli_paths(work: Path, dist: Path) -> None:
    """Reserve NEW external roots; never replace an earlier build or artifact."""
    if not work.is_absolute() or not dist.is_absolute():
        raise ValueError("CLI build paths must be absolute")
    work, dist = work.resolve(), dist.resolve()
    if (
        work == dist
        or work.is_relative_to(dist)
        or dist.is_relative_to(work)
        or work.is_relative_to(ROOT)
        or dist.is_relative_to(ROOT)
    ):
        raise ValueError("CLI build paths must be separate and outside the checkout")
    # Check both before either mkdir. No --clean, recursive delete or overwrite.
    if work.exists() or dist.exists():
        raise ValueError("CLI build destination already exists; choose a new candidate")
    work.mkdir(parents=True, exist_ok=False)
    dist.mkdir(parents=True, exist_ok=False)


def cli_build_command(work: Path, dist: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--workpath",
        str(work),
        "--distpath",
        str(dist),
        str(BUILD_DIR / "ytdl_cli.spec"),
    ]


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cli_components() -> list[dict]:
    # Source build entry (python build/build.py) needs the source root for the
    # canonical resolver. This is NOT PYTHONPATH or injection into the EXE child.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from src.infrastructure.ffmpeg import find_ffmpeg, find_ffprobe

    components = []
    expected = (ROOT / "vendor/ffmpeg/bin").resolve()
    for name, path in (("ffmpeg", find_ffmpeg()), ("ffprobe", find_ffprobe())):
        if path is None or path.resolve().parent != expected:
            raise ValueError("Only the provenance-admitted existing vendor FFmpeg is allowed")
        version = subprocess.run(
            [str(path), "-version"], capture_output=True, text=True, check=True, timeout=20
        ).stdout
        license_text = subprocess.run(
            [str(path), "-L"], capture_output=True, text=True, check=True, timeout=20
        ).stdout
        if (
            "--enable-gpl" in version
            or "--enable-nonfree" in version
            or "GNU Lesser General Public License" not in license_text
        ):
            raise ValueError("FFmpeg component is not an admitted LGPL-only configuration")
        components.append(
            {
                "name": name,
                "source": path.relative_to(ROOT).as_posix(),
                "sha256": file_hash(path),
                "size": path.stat().st_size,
                "version_and_configuration": version,
                "license_output": license_text,
                "license_source": "vendor/ffmpeg/LICENSE.txt",
            }
        )
    return components


def copy_cli_licenses(bundle: Path) -> list[dict]:
    destination = bundle / "licenses"
    destination.mkdir()
    pairs = [
        (ROOT / "vendor/ffmpeg/LICENSE.txt", "FFmpeg_LICENSE.txt"),
        (ROOT / "vendor/ffmpeg/LICENSE.txt", "LGPL-3.0.txt"),
        (Path(sys.base_prefix) / "LICENSE.txt", "Python_LICENSE.txt"),
    ]
    for component in ("fastmcp", "yt-dlp", "uvicorn", "pyinstaller"):
        distribution = metadata.distribution(component)
        candidates = [
            p
            for p in distribution.files or []
            if "/licenses/" in str(p).replace("\\", "/")
            and any(x in p.name.lower() for x in ("license", "copying", "notice"))
        ]
        if not candidates:
            raise ValueError("Required installed component license is unavailable")
        for i, relative in enumerate(candidates):
            name = (
                "PyInstaller_COPYING.txt"
                if component == "pyinstaller"
                else (f"{component}_{i}_{relative.name}")
            )
            pairs.append((Path(distribution.locate_file(relative)), name))
    # Validate the complete finite license list before copying any of it.
    if not all(path.is_file() for path, _ in pairs):
        raise ValueError("A required existing license text is unavailable")
    results = []
    for path, name in pairs:
        shutil.copy2(path, destination / name)
        results.append({"member": "licenses/" + name, "sha256": file_hash(path)})
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.txt", bundle / "THIRD_PARTY_NOTICES.txt")
    return results


def build_cli(work: Path, dist: Path) -> Path:
    reserve_cli_paths(work, dist)
    components = cli_components()
    command = cli_build_command(work, dist)
    subprocess.run(command, cwd=ROOT, check=True)
    bundle = dist / "YTDownloadCLI"
    if not (bundle / "ytdl.exe").is_file() or not (bundle / "_internal").is_dir():
        raise RuntimeError("PyInstaller did not produce the required console onedir")
    target = bundle / "vendor/ffmpeg/bin"
    target.mkdir(parents=True)
    for row in components:
        source = ROOT / row["source"]
        shutil.copy2(source, target / source.name)
    licenses = copy_cli_licenses(bundle)
    # This is the just-created owned bundle, not a recursive scan of the checkout.
    members = []
    for path in sorted(bundle.rglob("*")):
        if path.is_symlink() or path.is_junction():
            raise ValueError("Unexpected linked member in new artifact")
        if path.is_file():
            members.append(
                {
                    "path": path.relative_to(dist).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": file_hash(path),
                }
            )
    q2_paths = [
        "ytdl_cli.py",
        "build/ytdl_cli.spec",
        "build/build.py",
        "src/infrastructure/ffmpeg.py",
        "scripts/smoke_cli_exe.py",
        "tests/test_cli_packaging.py",
        "tests/test_ffmpeg_detection.py",
        "THIRD_PARTY_NOTICES.txt",
    ]
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    record = {
        "bundle": "YTDownloadCLI",
        "console": True,
        "onedir": True,
        "effective_accepted_prefix": revision,
        "q2_inputs": [{"path": p, "sha256": file_hash(ROOT / p)} for p in q2_paths],
        "build_argv": command,
        "python": sys.version,
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "pyinstaller": metadata.version("pyinstaller"),
        "components": components,
        "licenses": licenses,
        "members": members,
        "qualification": "Built only; native functional verification is a separate receipt",
        "external_youtube": "WAITING_FOR_USER_URL",
        "GUI": "not built or qualified",
    }
    with (dist / "artifact-manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2)
        stream.write("\n")
    print(f"Console onedir built: members={len(members)}")
    return bundle


def main(argv: list[str] | None = None) -> None:
    """Default GUI route is preserved; CLI uses separate explicit new roots."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("gui", "cli"), default="gui")
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--dist-dir", type=Path)
    args = parser.parse_args(argv)
    if args.target == "cli":
        if args.work_dir is None or args.dist_dir is None:
            parser.error("CLI target requires --work-dir and --dist-dir")
        build_cli(args.work_dir, args.dist_dir)
        return
    if args.work_dir is not None or args.dist_dir is not None:
        parser.error("Owned path options apply only to --target cli")
    print(f"ROOT: {ROOT}")
    print(f"DIST: {DIST_DIR}")

    run_pyinstaller()
    copy_ffmpeg_outside_internal()
    copy_licenses()
    print_summary()
    print("\n✅ Сборка завершена!")


if __name__ == "__main__":
    main()
