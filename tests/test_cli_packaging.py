"""Packaging contracts; real relocated artifact behavior is checked separately."""

from __future__ import annotations

import importlib.util
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def build_module():
    spec = importlib.util.spec_from_file_location("owned_build_contract", ROOT / "build/build.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wrapper_uses_canonical_cli_and_preserves_exit(monkeypatch):
    import src.interfaces.cli

    calls = []

    def canonical():
        calls.append("canonical")
        return 37

    monkeypatch.setattr(src.interfaces.cli, "main", canonical)
    with pytest.raises(SystemExit) as stop:
        runpy.run_path(str(ROOT / "ytdl_cli.py"), run_name="__main__")
    assert stop.value.code == 37 and calls == ["canonical"]


def test_console_spec_actual_wiring_onedir_entry_and_server_modules(monkeypatch):
    import PyInstaller.utils.hooks as hooks

    monkeypatch.setattr(hooks, "collect_submodules", lambda name: [name + ".owned"])
    monkeypatch.setattr(hooks, "collect_data_files", lambda name: [])
    monkeypatch.setattr(hooks, "copy_metadata", lambda *a, **kw: [])
    calls = {}

    def analysis(scripts, **kwargs):
        calls["analysis"] = (scripts, kwargs)
        return SimpleNamespace(pure=[], scripts=["entry"], binaries=["dll"], datas=["data"])

    def executable(*args, **kwargs):
        calls["exe"] = (args, kwargs)
        return "owned-executable"

    def collect(*args, **kwargs):
        calls["collect"] = (args, kwargs)

    runpy.run_path(
        str(ROOT / "build/ytdl_cli.spec"),
        init_globals={
            "SPECPATH": str(ROOT / "build"),
            "Analysis": analysis,
            "PYZ": lambda _: "pyz",
            "EXE": executable,
            "COLLECT": collect,
        },
    )
    assert calls["analysis"][0] == [str(ROOT / "ytdl_cli.py")]
    assert calls["exe"][1]["console"] is True
    assert calls["exe"][1]["exclude_binaries"] is True and calls["exe"][1]["name"] == "ytdl"
    assert calls["collect"][0] == ("owned-executable", ["dll"], ["data"])
    assert calls["collect"][1]["name"] == "YTDownloadCLI"
    assert "uvicorn.protocols.http.h11_impl" in calls["analysis"][1]["hiddenimports"]
    assert "anyio._backends._asyncio" in calls["analysis"][1]["hiddenimports"]
    from src.infrastructure.mcp.manifest import MCP_TOOL_MANIFEST

    assert {tool.registrar_module for tool in MCP_TOOL_MANIFEST} <= set(
        calls["analysis"][1]["hiddenimports"]
    )


@pytest.mark.parametrize("existing", ["work", "dist"])
def test_cli_build_refuses_existing_destination_before_effects(tmp_path, existing):
    module = build_module()
    work, dist = tmp_path / "work", tmp_path / "artifact"
    occupied = work if existing == "work" else dist
    occupied.mkdir()
    marker = occupied / "keep.bin"
    marker.write_bytes(b"existing preserved")
    with pytest.raises(ValueError, match="exist"):
        module.reserve_cli_paths(work, dist)
    assert marker.read_bytes() == b"existing preserved"
    assert not (dist if existing == "work" else work).exists()


@pytest.mark.parametrize("relation", ["same", "nested", "relative", "source"])
def test_cli_build_rejects_unsafe_path_relationships(tmp_path, relation):
    module = build_module()
    work, dist = tmp_path / "work", tmp_path / "artifact"
    if relation == "same":
        dist = work
    elif relation == "nested":
        dist = work / "nested"
    elif relation == "relative":
        work = Path("relative-q2-work")
    else:
        work = ROOT / "build/not-an-owned-build-destination"
    with pytest.raises(ValueError):
        module.reserve_cli_paths(work, dist)
    assert not (tmp_path / "work").exists() and not (tmp_path / "artifact").exists()


def test_cli_build_reserves_new_roots_and_builds_literal_console_argv(tmp_path):
    module = build_module()
    work, dist = tmp_path / "work with spaces", tmp_path / "artifact with spaces"
    module.reserve_cli_paths(work, dist)
    assert work.is_dir() and dist.is_dir() and list(work.iterdir()) == list(dist.iterdir()) == []
    command = module.cli_build_command(work, dist)
    assert command[1:3] == ["-m", "PyInstaller"]
    assert command[command.index("--workpath") + 1] == str(work)
    assert command[command.index("--distpath") + 1] == str(dist)
    assert command[-1] == str(ROOT / "build/ytdl_cli.spec")
    assert "--clean" not in command and "--noconfirm" not in command


def test_no_args_preserve_old_gui_route_without_executing_it(monkeypatch):
    module = build_module()
    seen = []
    for name in (
        "run_pyinstaller",
        "copy_ffmpeg_outside_internal",
        "copy_licenses",
        "print_summary",
    ):
        monkeypatch.setattr(module, name, lambda label=name: seen.append(label))
    module.main([])
    assert seen == [
        "run_pyinstaller",
        "copy_ffmpeg_outside_internal",
        "copy_licenses",
        "print_summary",
    ]


def test_native_artifact_environment_excludes_development_and_profile_overrides(
    monkeypatch, tmp_path
):
    from scripts.smoke_cli_exe import native_environment

    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "YTDL_FFMPEG_PATH", "YTDL_FFPROBE_PATH"):
        monkeypatch.setenv(key, "OWNED_UNWANTED_ENV_SENTINEL")
    env = native_environment(tmp_path / "selectors", tmp_path / "absent profile")
    assert not any("OWNED_UNWANTED_ENV_SENTINEL" in value for value in env.values())
    assert all(
        key not in env for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "YTDL_FFMPEG_PATH")
    )
    assert Path(env["YTDL_DATA_DIR"]) == (tmp_path / "absent profile").resolve()
    assert not (tmp_path / "absent profile").exists()
    assert Path(env["HOME"]).is_relative_to(tmp_path)
    assert str(ROOT) not in env["PATH"] and ".venv" not in env["PATH"]


def test_native_verifier_refuses_existing_output_before_launch(monkeypatch, tmp_path):
    from scripts import smoke_cli_exe

    root = tmp_path / "existing"
    root.mkdir()
    marker = root / "preserve.bin"
    marker.write_bytes(b"not an auto-clean root")

    def forbidden(*args, **kwargs):
        raise AssertionError("Native process must not start for an occupied output")

    monkeypatch.setattr(smoke_cli_exe.subprocess, "Popen", forbidden)
    with pytest.raises(SystemExit) as stop:
        smoke_cli_exe.main(["--exe", str(tmp_path / "ytdl.exe"), "--work-root", str(root)])
    assert stop.value.code == 2 and marker.read_bytes() == b"not an auto-clean root"
