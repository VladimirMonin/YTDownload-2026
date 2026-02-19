"""Виджет истории загрузок.

Классы:
    HistoryItemWidget: Карточка одной записи истории.
    HistoryWidget: Список записей истории.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...domain.models import HistoryEntry
from ...domain.models.download_task import DownloadStatus
from ..utils.tabler_icons import TablerIcons, get_icon
from ..utils.theme import get_color


class HistoryItemWidget(QFrame):
    """Карточка одной записи в истории.

    Signals:
        open_folder_requested(path): Открыть папку с файлом.
        delete_requested(entry_id, delete_files): Удалить запись.
    """

    open_folder_requested = Signal(Path)
    delete_requested = Signal(int, bool)  # (entry_id, delete_files_from_disk)

    def __init__(self, entry: HistoryEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self.setObjectName("card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Номер
        id_lbl = QLabel(f"#{self._entry.id}")
        id_lbl.setObjectName("secondary")
        id_lbl.setFixedWidth(36)
        layout.addWidget(id_lbl)

        # Иконка статуса
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(20, 20)
        icon_lbl.setPixmap(self._status_icon())
        layout.addWidget(icon_lbl)

        # Описание (бейдж + заголовок + мета)
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        # Первая строка: бейдж плейлиста (если есть) + заголовок
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        title_row.setContentsMargins(0, 0, 0, 0)

        is_playlist = bool(self._entry.playlist_title)
        if is_playlist:
            badge = QLabel()
            badge.setPixmap(get_icon(TablerIcons.PLAYLIST, size=14).pixmap(14, 14))
            badge.setFixedSize(14, 14)
            badge.setToolTip(self.tr("Плейлист"))
            title_row.addWidget(badge)

        # Заголовок для плейлиста показываем playlist_title, иначе title или URL
        display_title = (
            self._entry.playlist_title if is_playlist else (self._entry.title or self._entry.url)
        )
        title_lbl = QLabel(display_title)
        title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        title_lbl.setToolTip(self._entry.url)
        title_row.addWidget(title_lbl, 1)

        title_row_widget = QWidget()
        title_row_widget.setLayout(title_row)
        title_row_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        title_row_widget.setStyleSheet("background: transparent;")
        info_layout.addWidget(title_row_widget)

        # Мета-строка
        meta_parts = []
        if is_playlist:
            meta_parts.append(self.tr("Плейлист"))
        if self._entry.quality:
            meta_parts.append(self._entry.quality.value)
        if self._entry.download_type:
            meta_parts.append(
                self.tr("аудио") if self._entry.download_type.value == "audio" else self.tr("видео")
            )
        if self._entry.finished_at:
            meta_parts.append(self._entry.finished_at.strftime("%d.%m.%Y %H:%M"))

        meta_lbl = QLabel(" · ".join(meta_parts))
        meta_lbl.setObjectName("secondary")
        info_layout.addWidget(meta_lbl)

        layout.addLayout(info_layout, 1)

        # Статус
        status_lbl = QLabel(self._entry.status.display_name())
        status_lbl.setStyleSheet(f"color: {self._status_color()}; font-weight: 500;")
        layout.addWidget(status_lbl)

        # Кнопка «Открыть папку» — показываем если есть что открывать
        target_folder = self._resolve_folder()
        if target_folder:
            open_btn = QPushButton()
            open_btn.setObjectName("icon_btn")
            open_btn.setIcon(get_icon(TablerIcons.FOLDER_OPEN, size=16))
            open_btn.setFixedSize(28, 28)
            open_btn.setToolTip(self.tr("Открыть папку"))
            open_btn.clicked.connect(lambda _f=target_folder: self.open_folder_requested.emit(_f))
            layout.addWidget(open_btn)

        # Кнопка «Удалить»
        del_btn = QPushButton()
        del_btn.setObjectName("icon_btn")
        del_btn.setIcon(get_icon(TablerIcons.TRASH, size=16, color=get_color("error")))
        del_btn.setFixedSize(28, 28)
        del_btn.setToolTip(self.tr("Удалить из истории"))
        del_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(del_btn)

    def _resolve_folder(self) -> Path | None:
        """Определяет папку для открытия.

        Приоритет: output_dir → папка video_path → папка audio_path.

        Returns:
            Путь к папке или None.
        """
        if self._entry.output_dir and self._entry.output_dir.exists():
            return self._entry.output_dir
        file_path = self._entry.video_path or self._entry.audio_path
        if file_path and file_path.parent.exists():
            return file_path.parent
        return None

    def _on_delete_clicked(self) -> None:
        """Показывает диалог подтверждения удаления."""
        msg = QMessageBox(self)
        msg.setWindowTitle(self.tr("Удалить запись"))
        title_text = self._entry.playlist_title or self._entry.title or self._entry.url[:60]
        msg.setText(self.tr("Удалить запись «%1» из истории?").replace("%1", title_text))
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)

        cb = QCheckBox(self.tr("Удалить файлы с диска"))
        cb.setChecked(True)
        msg.setCheckBox(cb)

        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(self._entry.id, cb.isChecked())

    def _status_icon(self):
        if self._entry.status == DownloadStatus.DONE:
            return get_icon(TablerIcons.CIRCLE_CHECK, size=16, color=get_color("success")).pixmap(
                16, 16
            )
        elif self._entry.status == DownloadStatus.FAILED:
            return get_icon(TablerIcons.CIRCLE_X, size=16, color=get_color("error")).pixmap(16, 16)
        elif self._entry.status == DownloadStatus.CANCELLED:
            return get_icon(TablerIcons.X, size=16, color=get_color("text_disabled")).pixmap(16, 16)
        return get_icon(TablerIcons.LOADER, size=16).pixmap(16, 16)

    def _status_color(self) -> str:
        if self._entry.status == DownloadStatus.DONE:
            return get_color("success")
        elif self._entry.status == DownloadStatus.FAILED:
            return get_color("error")
        elif self._entry.status == DownloadStatus.CANCELLED:
            return get_color("text_disabled")
        return get_color("text_secondary")


class HistoryWidget(QWidget):
    """Список истории загрузок с поиском.

    Signals:
        open_folder_requested(path): Открыть папку.
        delete_requested(entry_id, delete_files): Удалить запись.
    """

    open_folder_requested = Signal(Path)
    delete_requested = Signal(int, bool)  # (entry_id, delete_files_from_disk)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[HistoryItemWidget] = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Поиск
        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(self.tr("Поиск по истории…"))
        self._search_edit.setMinimumHeight(36)
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setMaximumWidth(360)
        search_row.addWidget(self._search_edit)
        search_row.addStretch()
        layout.addLayout(search_row)

        # Скролл
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(6)
        self._container_layout.addStretch()

        scroll.setWidget(self._container)
        layout.addWidget(scroll, 1)

        # Соединяем поиск
        self._search_edit.textChanged.connect(self._on_search)

    def load_entries(self, entries: list[HistoryEntry]) -> None:
        """Заполняет список записями истории.

        Args:
            entries: Список записей (новые первыми).
        """
        # Очищаем
        while self._container_layout.count() > 1:
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._items.clear()

        for entry in entries:
            widget = HistoryItemWidget(entry)
            widget.open_folder_requested.connect(self.open_folder_requested)
            widget.delete_requested.connect(self.delete_requested)
            self._items.append(widget)
            self._container_layout.insertWidget(self._container_layout.count() - 1, widget)

    def _on_search(self, query: str) -> None:
        q = query.lower()
        for item in self._items:
            title_match = q in (item._entry.playlist_title or item._entry.title).lower()
            url_match = q in item._entry.url.lower()
            item.setVisible(not q or title_match or url_match)

    def update_icons(self) -> None:
        """Обновляет иконки при смене темы."""
        pass  # Иконки в item widgets создаются динамически
