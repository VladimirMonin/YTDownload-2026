"""Виджет ввода URL и добавления в очередь.

Классы:
    UrlInputWidget: Поле ввода URL с кнопкой добавления.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from ..utils.tabler_icons import TablerIcons, get_icon


class UrlInputWidget(QWidget):
    """Поле ввода URL YouTube с кнопкой «Добавить в очередь».

    Signals:
        add_requested(url): Пользователь нажал добавить с непустым URL.
    """

    add_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText(self.tr("Вставьте ссылку на YouTube видео или плейлист…"))
        self._url_edit.setMinimumHeight(40)
        self._url_edit.setClearButtonEnabled(True)
        layout.addWidget(self._url_edit, 1)

        self._add_btn = QPushButton(self.tr("Добавить"))
        self._add_btn.setObjectName("primary")
        self._add_btn.setMinimumHeight(40)
        self._add_btn.setMinimumWidth(120)
        self._add_btn.setIcon(get_icon(TablerIcons.DOWNLOAD, size=18, color="#ffffff"))
        layout.addWidget(self._add_btn)

    def _connect_signals(self) -> None:
        self._add_btn.clicked.connect(self._on_add)
        self._url_edit.returnPressed.connect(self._on_add)

    def _on_add(self) -> None:
        url = self._url_edit.text().strip()
        if url:
            self.add_requested.emit(url)
            self._url_edit.clear()

    def update_icons(self) -> None:
        """Обновляет иконки при смене темы."""
        self._add_btn.setIcon(get_icon(TablerIcons.DOWNLOAD, size=18, color="#ffffff"))

    def set_enabled(self, enabled: bool) -> None:
        """Включает/выключает поле ввода."""
        self._url_edit.setEnabled(enabled)
        self._add_btn.setEnabled(enabled)
