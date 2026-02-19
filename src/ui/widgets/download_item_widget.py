"""Карточка загрузки с прогресс-баром.

Классы:
    DownloadItemWidget: Карточка одной загрузки в очереди.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...domain.models import DownloadTask
from ...domain.models.download_task import DownloadStatus
from ..utils.tabler_icons import TablerIcons, get_icon
from ..utils.theme import get_color


def _format_speed(speed_bps: float) -> str:
    """Форматирует скорость в KB/s или MB/s."""
    if speed_bps <= 0:
        return ""
    if speed_bps >= 1024 * 1024:
        return f"{speed_bps / 1024 / 1024:.1f} МБ/с"
    return f"{speed_bps / 1024:.0f} КБ/с"


def _format_eta(eta_sec: int) -> str:
    """Форматирует оставшееся время."""
    if eta_sec <= 0:
        return ""
    m, s = divmod(eta_sec, 60)
    h, m = divmod(m, 60)
    if h:
        return f"~{h}ч {m}м"
    if m:
        return f"~{m}м {s}с"
    return f"~{s}с"


class DownloadItemWidget(QFrame):
    """Карточка одной загрузки с прогрессом и кнопкой отмены.

    Signals:
        cancel_requested(task_id): Пользователь нажал «Отмена».
    """

    cancel_requested = Signal(int)

    def __init__(self, task: DownloadTask, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._task_id = task.id
        self._init_ui(task)
        self.setObjectName("card")
        self.setFrameShape(QFrame.Shape.StyledPanel)

    def _init_ui(self, task: DownloadTask) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        # ── Верхняя строка: ID + Название + Кнопка отмены ──────────
        top = QHBoxLayout()
        top.setSpacing(8)

        self._id_label = QLabel(f"#{task.id}")
        self._id_label.setObjectName("secondary")
        self._id_label.setFixedWidth(36)
        top.addWidget(self._id_label)

        self._title_label = QLabel(task.title or task.url)
        self._title_label.setObjectName("title")
        self._title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._title_label.setWordWrap(False)
        self._title_label.setToolTip(task.url)
        top.addWidget(self._title_label, 1)

        self._status_label = QLabel(task.status.display_name())
        self._status_label.setObjectName("secondary")
        top.addWidget(self._status_label)

        self._cancel_btn = QPushButton()
        self._cancel_btn.setObjectName("icon_btn")
        self._cancel_btn.setIcon(get_icon(TablerIcons.X, size=16))
        self._cancel_btn.setFixedSize(28, 28)
        self._cancel_btn.setToolTip(self.tr("Отменить"))
        top.addWidget(self._cancel_btn)
        root.addLayout(top)

        # ── Прогресс-бар ────────────────────────────────────────────
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        root.addWidget(self._progress_bar)

        # ── Нижняя строка: URL + скорость + ETA ─────────────────────
        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        self._url_label = QLabel(task.url)
        self._url_label.setObjectName("secondary")
        self._url_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # Обрезаем длинные URL
        url_shown = task.url if len(task.url) <= 60 else task.url[:57] + "..."
        self._url_label.setText(url_shown)
        bottom.addWidget(self._url_label, 1)

        self._speed_label = QLabel("")
        self._speed_label.setObjectName("secondary")
        bottom.addWidget(self._speed_label)

        self._eta_label = QLabel("")
        self._eta_label.setObjectName("secondary")
        bottom.addWidget(self._eta_label)

        root.addLayout(bottom)

        # ── Коннекты ─────────────────────────────────────────────────
        self._cancel_btn.clicked.connect(lambda: self.cancel_requested.emit(self._task_id))

        self._apply_status(task.status)

    def update_task(self, task: DownloadTask) -> None:
        """Обновляет отображение задачи.

        Args:
            task: Обновлённая задача.
        """
        if task.title:
            self._title_label.setText(task.title)
        self._status_label.setText(task.status.display_name())
        self._progress_bar.setValue(int(task.progress))
        self._speed_label.setText(_format_speed(task.speed))
        self._eta_label.setText(_format_eta(task.eta_seconds))
        self._apply_status(task.status)

    def update_progress(self, percent: float, speed: float, eta: int) -> None:
        """Обновляет прогресс.

        Args:
            percent: Процент 0..100.
            speed: Скорость в байтах/сек.
            eta: Оставшееся время в секундах.
        """
        self._progress_bar.setValue(int(percent))
        self._speed_label.setText(_format_speed(speed))
        self._eta_label.setText(_format_eta(eta))

    def _apply_status(self, status: DownloadStatus) -> None:
        """Визуально подстраивает виджет под статус."""
        is_active = status.is_active()
        is_done = status == DownloadStatus.DONE
        is_failed = status == DownloadStatus.FAILED
        is_cancelled = status == DownloadStatus.CANCELLED

        # Кнопка отмены показывается только для не-финальных статусов
        can_cancel = not status.is_terminal()
        self._cancel_btn.setVisible(can_cancel)

        # Бар анимации
        if is_active:
            self._progress_bar.setRange(0, 100)
        elif status == DownloadStatus.QUEUED:
            self._progress_bar.setRange(0, 0)  # Indeterminate pulse

        # Цвет статуса
        if is_done:
            color = get_color("success")
        elif is_failed:
            color = get_color("error")
        elif is_cancelled:
            color = get_color("text_disabled")
        else:
            color = get_color("text_secondary")

        self._status_label.setStyleSheet(f"color: {color};")

    def update_icons(self) -> None:
        """Обновляет иконки при смене темы."""
        self._cancel_btn.setIcon(get_icon(TablerIcons.X, size=16))

    @property
    def task_id(self) -> int:
        return self._task_id
