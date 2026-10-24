"""Q1 characterizations: real wire/store/Qt boundaries, no network or visual UI."""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import threading
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QSignalSpy
from shiboken6 import isValid

from src.application.dto import DownloadSummaryDTO, QueryErrorDTO, serialize_for_transport
from src.application.history_semantics import resolve_history_entry_title
from src.bootstrap import create_runtime
from src.domain.models import AppSettings, HistoryEntry
from src.domain.models.app_settings import DownloadType, QualityOption
from src.domain.models.download_task import DownloadStatus
from src.infrastructure.mcp.server import create_mcp_server
from src.infrastructure.mcp.tools._utils import _fmt_dt
from src.ui.utils import tabler_icons, theme
from src.ui.utils.tabler_icons import TablerIcons, get_icon, get_pixmap
from src.ui.utils.theme import Theme, apply_theme, get_color
from src.ui.widgets.download_options_widget import DownloadOptionsWidget
from src.ui.widgets.history_widget import HistoryItemWidget, HistoryWidget
from tests.test_adapter_integration import GateEdge, child_env


@pytest.mark.parametrize(
    "enum,values",
    [
        (QualityOption, "best 1080p 720p 480p 360p audio"),
        (DownloadType, "video audio"),
        (DownloadStatus, "queued downloading merging done failed cancelled"),
        (Theme, "dark light"),
        (TablerIcons, "download upload cloud-download folder folder-open refresh player-stop "
         "player-play player-pause video movie music file-music volume volume-2 waveform "
         "file-text paragraph note check circle-check circle-x alert-circle alert-triangle "
         "info-circle loader list search settings settings-2 trash x chevron-down chevron-up "
         "chevron-left chevron-right playlist sun moon sun-moon clipboard copy clock bolt"),
    ],
)
def test_enum_legacy_value_hash_json_string_and_format(enum, values):
    assert [v.value for v in enum] == values.split()
    for member in enum:
        legacy = f"{enum.__name__}.{member.name}"
        assert member == member.value and hash(member) == hash(member.value)
        assert {member: 42}[member.value] == 42 and enum(member.value) is member
        assert json.loads(json.dumps({"value": member})) == {"value": member.value}
        assert (
            str(member) == legacy and f"{member}" == legacy
            and str.__mod__("%s", member) == legacy
        )
        assert format(member, ">40") == legacy.rjust(40)
    if enum is QualityOption:
        assert [v.display_name() for v in enum] == [
            "Лучшее", "1080p", "720p", "480p", "360p", "Только аудио",
        ]
    if enum is DownloadStatus:
        assert [v.display_name() for v in enum] == [
            "В очереди", "Загрузка...", "Сборка...", "Готово", "Ошибка", "Отменено",
        ]
        assert [v.value for v in enum if v.is_terminal()] == ["done", "failed", "cancelled"]
        assert [v.value for v in enum if v.is_active()] == ["downloading", "merging"]


def test_enums_actual_settings_history_json_reopen(tmp_path):
    profile = tmp_path / "profile"
    with create_runtime(profile) as runtime:
        for i, (quality, status) in enumerate(zip(QualityOption, DownloadStatus, strict=True), 1):
            kind = DownloadType.VIDEO if i % 2 else DownloadType.AUDIO
            settings = replace(runtime.api.get_settings(), quality=quality, download_type=kind,
                               output_dir=tmp_path / "output", theme=Theme.LIGHT.value)
            runtime.api.update_settings(settings)
            runtime.history_repo.add(HistoryEntry(id=i, url=f"https://example.invalid/{i}",
                title=f"Owned enum result {i}", quality=quality, download_type=kind, status=status))
        # Readonly reopen does not reinterpret saved nonterminal values as recovery.
    disk = (profile / "data/history.json").read_bytes()
    with create_runtime(profile, read_only=True) as reopened:
        saved = reopened.api.get_settings()
        assert saved.quality is QualityOption.AUDIO and saved.download_type is DownloadType.AUDIO
        assert saved.theme == "light"
        entries = sorted(reopened.api.list_history_entries(), key=lambda e: e.id)
        assert [e.status for e in entries] == list(DownloadStatus)
        assert [e.quality for e in entries] == list(QualityOption)
        assert [e.download_type for e in entries] == [DownloadType.VIDEO, DownloadType.AUDIO] * 3
    assert (profile / "data/history.json").read_bytes() == disk


@dataclass
class _NestedTransport:
    path: Path
    when: datetime
    mode: DownloadType
    optional: str | None
    values: tuple[int, bool, float]


def test_shared_serializer_actual_nested_dataclass_list_error_and_optional_fields(tmp_path):
    when = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    source = _NestedTransport(tmp_path / "owned", when, DownloadType.AUDIO, None, (0, False, 1.5))
    wire = json.loads(json.dumps(serialize_for_transport({"nested": [source]})))
    assert wire == {"nested": [{"path": str(source.path), "when": "2026-01-02T03:04:05+00:00",
                               "mode": "audio", "optional": None, "values": [0, False, 1.5]}]}
    assert serialize_for_transport(QueryErrorDTO("Owned refusal", "inspect", "NOT_FOUND")) == {
        "error": "Owned refusal", "hint": "inspect", "code": "NOT_FOUND"}
    dto = DownloadSummaryDTO(4, "https://example.invalid/4", "Owned summary", "", False,
                             "done", "720p", "video", when.isoformat(), None, "")
    legacy = serialize_for_transport(dto)
    fields = {"cancel_requested", "result_persisted", "error_code", "artifact_paths"}
    assert not fields.intersection(legacy)
    explicit = serialize_for_transport(replace(dto, cancel_requested=False,
        result_persisted=False, error_code="PERSISTENCE_FAILED", artifact_paths=[]))
    assert {k: explicit[k] for k in fields} == {"cancel_requested": False,
        "result_persisted": False, "error_code": "PERSISTENCE_FAILED", "artifact_paths": []}


def test_actual_sdk_nonempty_object_list_error_description_transcript_and_reopen(tmp_path):
    from fastmcp import Client

    output = tmp_path / "output"
    output.mkdir()
    media, desc, sub = output / "owned.mp4", output / "owned.description", output / "owned.en.vtt"
    media.write_bytes(b"Q1 synthetic media, not codec proof")
    desc.write_text("Distinct useful description — Q1", encoding="utf-8")
    transcript = "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nDistinct useful transcript\n"
    sub.write_text(transcript, encoding="utf-8")
    profile = tmp_path / "profile"
    with create_runtime(profile) as owner:
        owner.history_repo.add(HistoryEntry(
            id=17, url="https://example.invalid/owned", title="Owned Q1 result",
            quality=QualityOption.P720, download_type=DownloadType.VIDEO,
            status=DownloadStatus.DONE,
            output_dir=output, output_root=output, video_path=media, description_path=desc,
            subtitle_paths=[sub], artifact_paths=[media, desc, sub],
            created_at=datetime(2026, 1, 2, 3, 4, 5)))
        store = (profile / "data/history.json").read_bytes()
        server = create_mcp_server({"application_api": owner.api, "command_api": owner.api})

        async def query():
            async with Client(server) as client:
                obj = (await client.call_tool("get_download", {"id": 17})).structured_content
                assert (
                    obj["id"] == 17 and obj["title"] == "Owned Q1 result"
                    and obj["status"] == "done"
                )
                assert obj["quality"] == "720p" and obj["video_path"] == str(media)
                assert obj["created_at"] == "2026-01-02T03:04:05"
                assert obj["cancel_requested"] is None and obj["result_persisted"] is None
                assert obj["error_code"] is None and obj["artifact_paths"] == [
                    str(media), str(desc), str(sub),
                ]
                (tmp_path / "sdk-object.json").write_text(json.dumps(obj), encoding="utf-8")
                for name, args in [
                    ("list_downloads", {}), ("search_downloads", {"query": "Owned Q1"}),
                    ("search_with_description", {"query": "Owned Q1"}),
                ]:
                    rows = (await client.call_tool(name, args)).structured_content["result"]
                    assert len(rows) == 1 and rows[0]["id"] == 17
                    if name == "search_with_description":
                        assert rows[0]["description_text"] == "Distinct useful description — Q1"
                paths = (await client.call_tool("get_file_paths", {"id": 17})).structured_content
                assert paths["video_path"] == str(media) and paths["subtitle_paths"] == [str(sub)]
                description = (
                    await client.call_tool("read_description", {"id": 17})
                ).structured_content
                assert description["description_text"] == "Distinct useful description — Q1"
                text = (
                    await client.call_tool("get_transcript", {"id": 17, "lang": "en", "raw": True})
                ).structured_content
                assert text["transcript_text"] == transcript
                error = (await client.call_tool("get_download", {"id": 999})).structured_content
                assert error["code"] == "NOT_FOUND" and error["error"] and error["hint"]
            assert owner.api.get_download(17).title == "Owned Q1 result"

        asyncio.run(query())
        assert (profile / "data/history.json").read_bytes() == store
    with create_runtime(profile, read_only=True) as reopened:
        assert reopened.api.get_download(17).video_path == str(media)
    assert media.read_bytes() == b"Q1 synthetic media, not codec proof"
    assert desc.read_text(encoding="utf-8") == "Distinct useful description — Q1"


def test_live_sdk_optional_false_empty_unknown_then_persisted_readback(tmp_path):
    from fastmcp import Client

    entered, release = threading.Event(), threading.Event()
    profile, output = tmp_path / "profile", tmp_path / "output"
    with create_runtime(profile, backend_factory=lambda: GateEdge(entered, release)) as owner:
        owner.api.update_settings(replace(owner.api.get_settings(), output_dir=output))

        async def exercise():
            async with Client(create_mcp_server(owner.api)) as client:
                task_id = (await client.call_tool("add_download", {
                    "url": "https://example.invalid/owned-live-edge",
                    "quality": "720p", "download_type": "video",
                })).structured_content["task_id"]
                try:
                    assert entered.wait(2)
                    active = (
                        await client.call_tool("get_download", {"id": task_id})
                    ).structured_content
                    assert active["cancel_requested"] is False
                    assert active["result_persisted"] is None and active["error_code"] is None
                    assert active["artifact_paths"] == [] and active["status"] == "downloading"
                finally:
                    release.set()
                terminal = owner.api.wait_for_download(task_id, timeout=4)
                assert terminal.status == "done" and terminal.result_persisted is True
                done = (await client.call_tool("get_download", {"id": task_id})).structured_content
                assert done["cancel_requested"] is False and done["result_persisted"] is True
                assert done["artifact_paths"] == [str(output / f"download-{task_id}" / "owned.mp4")]
                media = Path(done["video_path"])
                assert media.read_bytes() == f"owned bridge media {task_id}".encode()
                (tmp_path / "sdk-live.json").write_text(
                    json.dumps({"active": active, "done": done}), encoding="utf-8",
                )
                return task_id
        try:
            task_id = asyncio.run(exercise())
        finally:
            release.set()
    with create_runtime(profile, read_only=True) as reopened:
        assert reopened.api.get_download(task_id).status == "done"
        assert (
            Path(reopened.api.get_download(task_id).video_path).read_bytes()
            == f"owned bridge media {task_id}".encode()
        )


def test_title_and_legacy_datetime_boundaries():
    for playlist, title, expected in [("Series", "Video", "Series"), ("", "Video", "Video"),
                                       (None, None, "u" * 80)]:
        entry = SimpleNamespace(playlist_title=playlist, title=title, url="u" * 95)
        assert resolve_history_entry_title(entry) == expected
    class ISOValue:
        def isoformat(self):
            return "2026-01-02T03:04:05"
    assert _fmt_dt(None) is None
    assert _fmt_dt("legacy date") == "legacy date"
    assert _fmt_dt(datetime(2026, 1, 2, 3, 4, 5)) == "2026-01-02T03:04:05"
    assert _fmt_dt(ISOValue()) == "2026-01-02T03:04:05"


def test_qt_real_selections_apply_settings_theme_palette_and_hidpi(
    qapp, qtbot, tmp_path, monkeypatch,
):
    original = theme._CURRENT_THEME
    widget = DownloadOptionsWidget(AppSettings(output_dir=tmp_path))
    qtbot.addWidget(widget)
    spy = QSignalSpy(widget.options_changed)
    try:
        for i, lang in enumerate(["ru", "en", "kk", "de", "fr", "es", "uk", "zh", "ja"]):
            q = list(QualityOption)[i % len(QualityOption)]
            kind = DownloadType.AUDIO if i % 2 else DownloadType.VIDEO
            widget.apply_settings(AppSettings(output_dir=tmp_path, quality=q, download_type=kind,
                subtitle_lang=lang, save_subtitles=bool(i % 2),
                save_description=False, save_thumbnail=False))
            assert (
                widget.quality is q and widget.download_type is kind
                and widget.subtitle_lang == lang
            )
            assert (
                widget.save_subtitles == bool(i % 2)
                and widget._lang_combo.isEnabled() == bool(i % 2)
            )
            assert not widget.save_description and not widget.save_thumbnail
        assert spy.count() > 0
        for chosen, text in [(Theme.DARK, "#e8eaf6"), (Theme.LIGHT, "#1a1d27")]:
            apply_theme(chosen)
            assert qapp.styleSheet() and get_color("text_primary") == text
            assert get_color("unknown-key", chosen) == "#ffffff"
            pix = get_pixmap(TablerIcons.DOWNLOAD, size=24)
            assert not pix.isNull() and not get_icon(TablerIcons.DOWNLOAD).isNull()
            assert pix.devicePixelRatio() == qapp.devicePixelRatio()
            assert pix.width() == int(24 * qapp.devicePixelRatio())
            image = pix.toImage()
            assert any(
                image.pixelColor(x, y).alpha()
                for x in range(image.width()) for y in range(image.height())
            )
        def unavailable(_):
            raise LookupError("owned theme-color fallback")
        monkeypatch.setattr(theme, "get_color", unavailable)
        assert tabler_icons._get_auto_color() == qapp.palette().text().color().name()
    finally:
        apply_theme(original)


@pytest.mark.parametrize("invalid", [None, 42])
def test_qt_invalid_language_has_explicit_boundary_error(qapp, qtbot, tmp_path, invalid):
    widget = DownloadOptionsWidget(AppSettings(output_dir=tmp_path))
    qtbot.addWidget(widget)
    widget._lang_combo.setItemData(0, invalid)
    widget._lang_combo.setCurrentIndex(0)
    with pytest.raises(TypeError, match="language"):
        _ = widget.subtitle_lang


@pytest.mark.parametrize("mode", ["absent", "core"])
def test_theme_without_widget_application_in_separate_native_process(tmp_path, mode):
    script = """
import json, sys
from PySide6.QtCore import QCoreApplication
from src.ui.utils import theme, tabler_icons
app = QCoreApplication([]) if sys.argv[1] == 'core' else None
theme.apply_theme(theme.Theme.LIGHT)
assert theme.get_color('text_primary') == '#1a1d27'
def unavailable(_): raise LookupError('owned fallback')
theme.get_color = unavailable
assert tabler_icons._get_auto_color() == '#e8eaf6'
assert QCoreApplication.instance() is app
print(json.dumps({'boundary':sys.argv[1],'next_operation':True}))
"""
    env = child_env(tmp_path / "selectors", tmp_path / "profile")
    result = subprocess.run(
        [sys.executable, "-c", script, mode], env=env, capture_output=True, text=True, timeout=20,
    )
    (tmp_path / "qt-child.json").write_text(json.dumps({"native_exit": result.returncode,
        "stdout": result.stdout, "stderr": result.stderr}), encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"boundary": mode, "next_operation": True}


def test_history_real_reload_filter_empty_and_deferred_widget_cleanup(qapp, qtbot):
    widget = HistoryWidget()
    qtbot.addWidget(widget)
    entries = [HistoryEntry(id=i, url=f"https://example.invalid/{i}", title=f"Owned {i}", status=s)
               for i, s in enumerate(DownloadStatus, 1)]
    widget.load_entries(entries)
    assert len(widget._items) == 6
    assert all(isinstance(item._status_icon(), QPixmap) for item in widget._items)
    previous = list(widget._items)
    widget._search_edit.setText("Owned 4")
    widget.load_entries(list(reversed(entries)))
    assert widget._search_edit.text() == "Owned 4"
    assert [w._entry.id for w in widget._items if not w.isHidden()] == [4]
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not any(isValid(w) for w in previous)
    current = list(widget._items)
    widget.load_entries([])
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not widget._items and not any(isValid(w) for w in current)
    widget.load_entries(entries[:1])
    widget._search_edit.clear()
    assert len(widget.findChildren(HistoryItemWidget)) == 1
    assert widget._items[0]._entry.id == 1 and not widget._items[0].isHidden()
