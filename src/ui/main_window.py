"""Главное окно приложения.

Классы:
    MainWindow: Тонкий оркестратор — shell + wiring.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..application.download_coordinator import DownloadCoordinator
from ..core.event_bus import EventBus
from ..domain.models.app_settings import AppSettings
from ..domain.models.download_task import DownloadTask, DownloadStatus
from ..domain.protocols.history_repository import IHistoryRepository
from ..domain.protocols.settings_repository import ISettingsRepository
from .managers import DownloadManager, HistoryManager
from .utils.tabler_icons import TablerIcons, get_icon
from .utils.theme import Theme, apply_theme, current_theme
from .widgets.download_item_widget import DownloadItemWidget
from .widgets.download_options_widget import DownloadOptionsWidget
from .widgets.history_widget import HistoryWidget
from .widgets.settings_dialog import SettingsDialog
from .widgets.url_input_widget import UrlInputWidget

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Главное окно YT Downloader.

    Тонкий оркестратор: создаёт виджеты, менеджеры, связывает сигналы.
    Бизнес-логика — в слоях ниже.
    """

    def __init__(
        self,
        services: dict,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings: AppSettings = services["settings"]
        self._settings_repo: ISettingsRepository = services["settings_repo"]
        self._history_repo: IHistoryRepository = services["history_repo"]
        self._coordinator: DownloadCoordinator = services["coordinator"]
        self._event_bus: EventBus = services["event_bus"]

        # Менеджеры
        self._download_manager = DownloadManager(self._coordinator, self._event_bus)
        self._history_manager = HistoryManager(self._history_repo, self._event_bus)

        # Карточки загрузок: task_id → DownloadItemWidget
        self._item_widgets: dict[int, DownloadItemWidget] = {}

        self._init_ui()
        self._connect_signals()
        self._restore_geometry()
        self._refresh_history()

        apply_theme(Theme(self._settings.theme))
        logger.info("ui.main_window.ready")

    # ─────────────────────────────────────────────────────────────────
    # UI Shell
    # ─────────────────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        self.setWindowTitle("YT Downloader")
        self.setMinimumSize(600, 700)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        # Заголовок
        root.addLayout(self._build_header())

        # URL ввод
        self._url_input = UrlInputWidget()
        root.addWidget(self._url_input)

        # Опции загрузки
        self._options = DownloadOptionsWidget(self._settings)
        root.addWidget(self._options)

        # Разделитель
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(line)

        # Вкладки
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        # Вкладка «Загрузки»
        self._queue_tab = self._build_queue_tab()
        self._tabs.addTab(self._queue_tab, "")
        self._tabs.setTabIcon(0, get_icon(TablerIcons.DOWNLOAD, size=16))
        self._tabs.setTabText(0, self.tr("Очередь"))

        # Вкладка «История»
        self._history_widget = HistoryWidget()
        self._tabs.addTab(self._history_widget, "")
        self._tabs.setTabIcon(1, get_icon(TablerIcons.HISTORY, size=16))
        self._tabs.setTabText(1, self.tr("История"))

        root.addWidget(self._tabs, 1)

        # Статус-бар
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage(self.tr("Готов"))

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        # Иконка + название
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_icon(TablerIcons.CLOUD_DOWNLOAD, size=28).pixmap(28, 28))
        layout.addWidget(icon_lbl)

        title_lbl = QLabel(self.tr("YT Downloader"))
        title_lbl.setObjectName("title")
        layout.addWidget(title_lbl)

        layout.addStretch()

        # Кнопка темы
        self._theme_btn = QPushButton()
        self._theme_btn.setObjectName("icon_btn")
        self._theme_btn.setFixedSize(36, 36)
        self._theme_btn.setToolTip(self.tr("Переключить тему"))
        self._update_theme_btn_icon()
        layout.addWidget(self._theme_btn)

        # Кнопка настроек
        self._settings_btn = QPushButton()
        self._settings_btn.setObjectName("icon_btn")
        self._settings_btn.setFixedSize(36, 36)
        self._settings_btn.setIcon(get_icon(TablerIcons.SETTINGS, size=20))
        self._settings_btn.setToolTip(self.tr("Настройки"))
        layout.addWidget(self._settings_btn)

        return layout

    def _build_queue_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(6)

        # Кол-во активных
        self._queue_info_lbl = QLabel(self.tr("Очередь пуста"))
        self._queue_info_lbl.setObjectName("secondary")
        layout.addWidget(self._queue_info_lbl)

        # Скролл-зона для карточек
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._queue_container = QWidget()
        self._queue_layout = QVBoxLayout(self._queue_container)
        self._queue_layout.setContentsMargins(0, 0, 4, 0)
        self._queue_layout.setSpacing(6)
        self._queue_layout.addStretch()

        scroll.setWidget(self._queue_container)
        layout.addWidget(scroll, 1)
        return tab

    # ─────────────────────────────────────────────────────────────────
    # Signal Wiring
    # ─────────────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._url_input.add_requested.connect(self._on_add_url)
        self._theme_btn.clicked.connect(self._on_toggle_theme)
        self._settings_btn.clicked.connect(self._on_open_settings)

        # DownloadManager → UI (уже в Main Thread через Qt Signals)
        self._download_manager.task_queued.connect(self._on_task_queued)
        self._download_manager.task_started.connect(self._on_task_started)
        self._download_manager.task_progress.connect(self._on_task_progress)
        self._download_manager.task_done.connect(self._on_task_done)
        self._download_manager.task_failed.connect(self._on_task_failed)
        self._download_manager.task_cancelled.connect(self._on_task_cancelled)
        self._download_manager.task_title_updated.connect(self._on_task_title_updated)

        # История — убираем сломанный callback из фонового потока
        self._history_widget.open_folder_requested.connect(self._open_folder)
        self._history_widget.delete_requested.connect(self._on_history_delete)

    # ─────────────────────────────────────────────────────────────────
    # Слоты (Main Thread)
    # ─────────────────────────────────────────────────────────────────

    def _on_add_url(self, url: str) -> None:
        task_id = self._download_manager.add(
            url=url,
            quality=self._options.quality,
            download_type=self._options.download_type,
            subtitle_lang=self._options.subtitle_lang,
            save_subtitles=self._options.save_subtitles,
            save_description=self._options.save_description,
            save_thumbnail=self._options.save_thumbnail,
        )
        logger.info("ui.add_url task_id=%d", task_id)

    def _on_task_queued(self, task_id: int, url: str) -> None:
        task = self._coordinator.get_task(task_id)
        if task is None:
            task = DownloadTask(id=task_id, url=url)

        item = DownloadItemWidget(task)
        item.cancel_requested.connect(self._download_manager.cancel)
        self._item_widgets[task_id] = item
        # Вставляем перед stretch
        self._queue_layout.insertWidget(self._queue_layout.count() - 1, item)
        self._update_queue_info()
        # Переключаемся на вкладку очереди
        self._tabs.setCurrentIndex(0)

    def _on_task_started(self, task_id: int) -> None:
        task = self._coordinator.get_task(task_id)
        if task and task_id in self._item_widgets:
            self._item_widgets[task_id].update_task(task)
        self._status_bar.showMessage(self.tr("Загрузка #%1…").replace("%1", str(task_id)))

    def _on_task_progress(self, task_id: int, percent: float, speed: float, eta: int) -> None:
        if task_id in self._item_widgets:
            self._item_widgets[task_id].update_progress(percent, speed, eta)

    def _on_task_done(self, task_id: int) -> None:
        task = self._coordinator.get_task(task_id)
        if task and task_id in self._item_widgets:
            self._item_widgets[task_id].update_task(task)
        self._update_queue_info()
        self._refresh_history()  # <-- главный поток, безопасно
        # Показываем куда сохранено
        entry = self._history_repo.get_by_id(task_id)
        path = entry.video_path or entry.audio_path if entry else None
        folder = str(path.parent) if path else str(self._settings.output_dir)
        self._status_bar.showMessage(
            self.tr("Загрузка #%1 готова → %2").replace("%1", str(task_id)).replace("%2", folder),
            10000,
        )

    def _on_task_failed(self, task_id: int, error: str) -> None:
        task = self._coordinator.get_task(task_id)
        if task and task_id in self._item_widgets:
            self._item_widgets[task_id].update_task(task)
        self._update_queue_info()
        self._refresh_history()  # <-- главный поток, безопасно
        self._status_bar.showMessage(
            self.tr("Ошибка #%1: %2").replace("%1", str(task_id)).replace("%2", error[:60]),
            8000,
        )
        logger.warning("ui.task_failed id=%d", task_id)

    def _on_task_cancelled(self, task_id: int) -> None:
        task = self._coordinator.get_task(task_id)
        if task and task_id in self._item_widgets:
            self._item_widgets[task_id].update_task(task)
        self._update_queue_info()
        self._refresh_history()  # <-- главный поток, безопасно

    def _on_task_title_updated(self, task_id: int, title: str) -> None:
        if task_id in self._item_widgets:
            self._item_widgets[task_id]._title_label.setText(title)

    def _on_toggle_theme(self) -> None:
        new_theme = Theme.LIGHT if current_theme() == Theme.DARK else Theme.DARK
        apply_theme(new_theme)
        self._settings.theme = new_theme.value
        self._settings_repo.save(self._settings)
        self._update_theme_btn_icon()
        self._update_all_icons()

    def _on_open_settings(self) -> None:
        dlg = SettingsDialog(self._settings, self)
        dlg.settings_saved.connect(self._on_settings_saved)
        dlg.exec()

    def _on_settings_saved(self, settings: AppSettings) -> None:
        self._settings = settings
        self._settings_repo.save(settings)
        self._coordinator.update_settings(settings)
        self._options.apply_settings(settings)
        apply_theme(Theme(settings.theme))
        self._update_theme_btn_icon()
        self._update_all_icons()
        logger.info("ui.settings_saved")

    def _open_folder(self, path: Path) -> None:
        """Открывает папку в системном файловом менеджере."""
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except Exception:
            logger.error("ui.open_folder.failed", exc_info=True)

    def _on_history_delete(self, entry_id: int, delete_files: bool) -> None:
        """Обрабатывает запрос удаления записи истории.

        Args:
            entry_id: ID записи.
            delete_files: Удалить файлы с диска вместе с записью.
        """
        if delete_files:
            entry = self._history_repo.get_by_id(entry_id)
            if entry:
                folder = (
                    entry.output_dir
                    or (entry.video_path.parent if entry.video_path else None)
                    or (entry.audio_path.parent if entry.audio_path else None)
                )
                if folder and folder.exists():
                    try:
                        shutil.rmtree(folder)
                        logger.info(
                            "ui.history_delete.files_removed id=%d path=%s", entry_id, folder
                        )
                    except Exception:
                        logger.error("ui.history_delete.files_failed id=%d", entry_id, exc_info=True)

        self._history_manager.delete(entry_id)
        self._refresh_history()
        logger.info("ui.history_delete id=%d delete_files=%s", entry_id, delete_files)

    # ─────────────────────────────────────────────────────────────────
    # Вспомогательные методы
    # ─────────────────────────────────────────────────────────────────

    def _update_queue_info(self) -> None:
        total = len(self._item_widgets)
        if total == 0:
            self._queue_info_lbl.setText(self.tr("Очередь пуста"))
        else:
            active = sum(1 for t in self._coordinator.get_tasks() if t.status.is_active())
            self._queue_info_lbl.setText(
                self.tr("%1 загрузок, %2 активных")
                .replace("%1", str(total))
                .replace("%2", str(active))
            )

    def _update_theme_btn_icon(self) -> None:
        icon = TablerIcons.MOON if current_theme() == Theme.DARK else TablerIcons.SUN
        self._theme_btn.setIcon(get_icon(icon, size=20))

    def _update_all_icons(self) -> None:
        """Обновляет иконки всех виджетов при смене темы."""
        self._url_input.update_icons()
        self._settings_btn.setIcon(get_icon(TablerIcons.SETTINGS, size=20))
        for widget in self._item_widgets.values():
            widget.update_icons()
        self._tabs.setTabIcon(0, get_icon(TablerIcons.DOWNLOAD, size=16))
        self._tabs.setTabIcon(1, get_icon(TablerIcons.HISTORY, size=16))

    def _refresh_history(self) -> None:
        entries = self._history_manager.get_all()
        self._history_widget.load_entries(entries)

    def _refresh_history_later(self) -> None:
        """Обновляет историю через QTimer (из фонового потока безопасно)."""
        QTimer.singleShot(0, self._refresh_history)

    def _restore_geometry(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            w = min(760, geo.width() - 40)
            h = min(900, geo.height() - 40)
            x = (geo.width() - w) // 2
            y = (geo.height() - h) // 2
            self.setGeometry(x, y, w, h)

    # ─────────────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        self._download_manager.cleanup()
        self._history_manager.cleanup()
        self._coordinator.shutdown()
        super().closeEvent(event)
