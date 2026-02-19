"""Утилиты для работы с иконками Tabler Icons.

Функции:
    get_icon: Возвращает QIcon из SVG файла.
    get_pixmap: Возвращает QPixmap из SVG файла.

Классы:
    TablerIcons: Перечисление доступных иконок.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

# Папка с SVG иконками
_ICONS_DIR = Path(__file__).parent.parent.parent.parent / "resources" / "icons" / "tabler"


class TablerIcons(str, Enum):
    """Доступные иконки Tabler Icons."""

    # Загрузка и управление
    DOWNLOAD = "download"
    UPLOAD = "upload"
    CLOUD_DOWNLOAD = "cloud-download"
    FOLDER = "folder"
    FOLDER_OPEN = "folder-open"
    REFRESH = "refresh"
    PLAYER_STOP = "player-stop"
    PLAYER_PLAY = "player-play"
    PLAYER_PAUSE = "player-pause"

    # Медиафайлы
    VIDEO = "video"
    MOVIE = "movie"
    MUSIC = "music"
    FILE_MUSIC = "file-music"
    VOLUME = "volume"
    VOLUME_2 = "volume-2"
    WAVEFORM = "waveform"

    # Субтитры и текст
    FILE_TEXT = "file-text"
    PARAGRAPH = "paragraph"
    NOTE = "note"

    # Состояния
    CHECK = "check"
    CIRCLE_CHECK = "circle-check"
    CIRCLE_X = "circle-x"
    ALERT_CIRCLE = "alert-circle"
    ALERT_TRIANGLE = "alert-triangle"
    INFO_CIRCLE = "info-circle"
    LOADER = "loader"

    # Навигация и UI
    LIST = "list"
    SEARCH = "search"
    SETTINGS = "settings"
    SETTINGS_2 = "settings-2"
    TRASH = "trash"
    X = "x"
    CHEVRON_DOWN = "chevron-down"
    CHEVRON_UP = "chevron-up"
    CHEVRON_LEFT = "chevron-left"
    CHEVRON_RIGHT = "chevron-right"
    PLAYLIST = "playlist"

    # Тема
    SUN = "sun"
    MOON = "moon"
    SUN_MOON = "sun-moon"

    # Разное
    CLIPBOARD = "clipboard"
    COPY = "copy"
    HISTORY = "clock"
    BOLT = "bolt"


def _icon_path(icon: TablerIcons) -> Path:
    """Возвращает путь к SVG файлу иконки."""
    return _ICONS_DIR / f"{icon.value}.svg"


def _get_auto_color() -> str:
    """Определяет цвет иконки из текущей темы приложения."""
    try:
        from .theme import get_color  # noqa: PLC0415
        return get_color("text_primary")
    except Exception:
        pass
    app = QApplication.instance()
    if app:
        palette = app.palette()
        return palette.text().color().name()
    return "#e8eaf6"


def _render_svg(icon: TablerIcons, size: int, color: Optional[str] = None) -> QPixmap:
    """Рендерит SVG с заменой цвета.

    Args:
        icon: Иконка для рендера.
        size: Размер в пикселях.
        color: Цвет в hex (#RRGGBB) или None для автоопределения.

    Returns:
        Отрендеренный QPixmap.
    """
    svg_path = _icon_path(icon)
    if not svg_path.exists():
        # Возвращаем пустой пиксмап если иконка не найдена
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        return pm

    # Читаем SVG и заменяем currentColor
    svg_content = svg_path.read_bytes()
    final_color = color or _get_auto_color()
    svg_modified = svg_content.replace(
        b"currentColor",
        final_color.encode("ascii"),
    )

    renderer = QSvgRenderer(svg_modified)

    # HiDPI: рендерим в размер с учётом device pixel ratio
    app = QApplication.instance()
    dpr = app.devicePixelRatio() if app else 1.0
    phys = QSize(int(size * dpr), int(size * dpr))
    pixmap = QPixmap(phys)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def get_pixmap(
    icon: TablerIcons,
    size: int = 20,
    color: Optional[str] = None,
) -> QPixmap:
    """Возвращает QPixmap для иконки.

    Автоматически подбирает цвет из текущей темы, если color не указан.

    Args:
        icon: Иконка.
        size: Размер в пикселях.
        color: Цвет или None (автоопределение из темы).

    Returns:
        QPixmap.
    """
    return _render_svg(icon, size, color)


def get_icon(
    icon: TablerIcons,
    size: int = 20,
    color: Optional[str] = None,
) -> QIcon:
    """Возвращает QIcon для кнопок и пр.

    Args:
        icon: Иконка.
        size: Размер в пикселях.
        color: Цвет или None (автоопределение из темы).

    Returns:
        QIcon.
    """
    return QIcon(get_pixmap(icon, size, color))
