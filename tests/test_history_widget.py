from __future__ import annotations

from src.domain.models import HistoryEntry
from src.ui.widgets.history_widget import HistoryWidget


def _visible_ids(widget: HistoryWidget) -> list[int]:
    return [item._entry.id for item in widget._items if item.isVisible()]


def test_history_search_filter_survives_reload(qtbot) -> None:
    widget = HistoryWidget()
    qtbot.addWidget(widget)
    widget.show()

    entries = [
        HistoryEntry(id=1, url="https://example.com/alpha", title="Alpha video"),
        HistoryEntry(id=2, url="https://example.com/python", title="Python lesson"),
    ]

    widget.load_entries(entries)
    widget._search_edit.setText("python")
    qtbot.waitUntil(lambda: _visible_ids(widget) == [2])

    widget.load_entries(entries)

    qtbot.waitUntil(lambda: _visible_ids(widget) == [2])


def test_history_search_matches_playlist_title_semantics(qtbot) -> None:
    widget = HistoryWidget()
    qtbot.addWidget(widget)
    widget.show()

    entries = [
        HistoryEntry(
            id=10,
            url="https://example.com/item",
            title="Episode 1",
            playlist_title="Python Backend Course",
        ),
        HistoryEntry(id=11, url="https://example.com/other", title="Other"),
    ]

    widget.load_entries(entries)
    widget._search_edit.setText("backend course")

    qtbot.waitUntil(lambda: _visible_ids(widget) == [10])
