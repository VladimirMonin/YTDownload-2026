"""Управление темами оформления приложения.

Классы:
    Theme: Темновая/светлая тема.

Функции:
    apply_theme: Применяет тему к приложению.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

# Абсолютный путь к check_white.svg (для QSS url())
# Qt в url() принимает POSIX-путь: C:/PY/... или ///C:/PY/...
# НЕ добавляем одиночный / — это создаёт /C:/PY/... → Qt дублирует диск
_CHECK_SVG = (
    Path(__file__).parent.parent.parent.parent / "resources" / "icons" / "check_white.svg"
).as_posix()


class Theme(str, Enum):
    """Варианты темы оформления."""

    DARK = "dark"
    LIGHT = "light"


# Цветовые константы тёмной темы
_DARK = {
    "bg_window": "#1a1d27",
    "bg_surface": "#242736",
    "bg_card": "#2d3048",
    "bg_input": "#1e2130",
    "border": "#3a3f5c",
    "border_focus": "#5c6bc0",
    "text_primary": "#e8eaf6",
    "text_secondary": "#9fa8da",
    "text_disabled": "#546E7A",
    "accent": "#5c6bc0",
    "accent_hover": "#7986cb",
    "accent_pressed": "#4a5ab3",
    "success": "#66bb6a",
    "warning": "#ffa726",
    "error": "#ef5350",
    "progress_bg": "#2d3048",
    "progress_chunk": "#5c6bc0",
    "scrollbar": "#3a3f5c",
    "scrollbar_hover": "#5c6bc0",
}

# Цветовые константы светлой темы
_LIGHT = {
    "bg_window": "#f5f5f5",
    "bg_surface": "#ffffff",
    "bg_card": "#f0f2f5",
    "bg_input": "#ffffff",
    "border": "#d1d5db",
    "border_focus": "#4a90d9",
    "text_primary": "#1a1d27",
    "text_secondary": "#6b7280",
    "text_disabled": "#9ca3af",
    "accent": "#4a90d9",
    "accent_hover": "#5ba5ec",
    "accent_pressed": "#3a7bc8",
    "success": "#4caf50",
    "warning": "#ff9800",
    "error": "#f44336",
    "progress_bg": "#e0e4ef",
    "progress_chunk": "#4a90d9",
    "scrollbar": "#d1d5db",
    "scrollbar_hover": "#4a90d9",
}


def _make_stylesheet(c: dict) -> str:
    """Генерирует QSS stylesheet из словаря цветов."""
    return f"""
/* === Global === */
QWidget {{
    background-color: {c["bg_window"]};
    color: {c["text_primary"]};
    font-family: "Noto Sans", "Segoe UI", sans-serif;
    font-size: 13px;
    border: none;
}}

/* === Main Window === */
QMainWindow {{
    background-color: {c["bg_window"]};
}}

/* === Скроллируемые области === */
QScrollArea {{
    background-color: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

/* === Фреймы / панели === */
QFrame#card {{
    background-color: {c["bg_card"]};
    border: 1px solid {c["border"]};
    border-radius: 8px;
}}
QFrame#surface {{
    background-color: {c["bg_surface"]};
    border-radius: 8px;
}}

/* === Кнопки === */
QPushButton {{
    background-color: {c["bg_card"]};
    color: {c["text_primary"]};
    border: 1px solid {c["border"]};
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {c["border"]};
    border-color: {c["border_focus"]};
}}
QPushButton:pressed {{
    background-color: {c["accent_pressed"]};
}}
QPushButton:disabled {{
    color: {c["text_disabled"]};
    border-color: {c["border"]};
}}
QPushButton#primary {{
    background-color: {c["accent"]};
    color: #ffffff;
    border: none;
}}
QPushButton#primary:hover {{
    background-color: {c["accent_hover"]};
}}
QPushButton#primary:pressed {{
    background-color: {c["accent_pressed"]};
}}
QPushButton#danger {{
    background-color: transparent;
    color: {c["error"]};
    border: 1px solid {c["error"]};
}}
QPushButton#danger:hover {{
    background-color: {c["error"]};
    color: white;
}}
QPushButton#icon_btn {{
    background-color: transparent;
    border: none;
    padding: 4px;
    border-radius: 4px;
}}
QPushButton#icon_btn:hover {{
    background-color: {c["bg_card"]};
}}

/* === Поля ввода === */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {c["bg_input"]};
    color: {c["text_primary"]};
    border: 1px solid {c["border"]};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {c["accent"]};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {c["border_focus"]};
}}
QLineEdit:disabled {{
    color: {c["text_disabled"]};
}}

/* === Выпадающий список === */
QComboBox {{
    background-color: {c["bg_input"]};
    color: {c["text_primary"]};
    border: 1px solid {c["border"]};
    border-radius: 6px;
    padding: 5px 10px;
    min-width: 80px;
}}
QComboBox:hover {{
    border-color: {c["border_focus"]};
}}
QComboBox:focus {{
    border-color: {c["border_focus"]};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {c["bg_surface"]};
    color: {c["text_primary"]};
    border: 1px solid {c["border"]};
    selection-background-color: {c["accent"]};
    selection-color: white;
    border-radius: 4px;
    outline: none;
}}

/* === Чекбокс === */
QCheckBox {{
    color: {c["text_primary"]};
    spacing: 8px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {c["border"]};
    border-radius: 3px;
    background-color: {c["bg_input"]};
}}
QCheckBox::indicator:checked {{
    background-color: {c["accent"]};
    border-color: {c["accent"]};
    image: url({_CHECK_SVG});
}}
QCheckBox::indicator:hover {{
    border-color: {c["border_focus"]};
}}
QCheckBox::indicator:checked:hover {{
    background-color: {c["accent_hover"]};
    border-color: {c["accent_hover"]};
    image: url({_CHECK_SVG});
}}

/* === Прогрессбар === */
QProgressBar {{
    background-color: {c["progress_bg"]};
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {c["progress_chunk"]};
    border-radius: 4px;
}}

/* === Метки === */
QLabel {{
    background: transparent;
    color: {c["text_primary"]};
}}
QLabel#secondary {{
    color: {c["text_secondary"]};
    font-size: 11px;
}}
QLabel#title {{
    font-size: 16px;
    font-weight: 600;
}}
QLabel#subtitle {{
    font-size: 12px;
    color: {c["text_secondary"]};
}}

/* === Вкладки === */
QTabWidget::pane {{
    border: 1px solid {c["border"]};
    border-radius: 8px;
    background-color: {c["bg_surface"]};
}}
QTabBar::tab {{
    background-color: transparent;
    color: {c["text_secondary"]};
    padding: 8px 20px;
    border-bottom: 2px solid transparent;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    color: {c["text_primary"]};
    border-bottom: 2px solid {c["accent"]};
}}
QTabBar::tab:hover:!selected {{
    color: {c["text_primary"]};
}}

/* === Список === */
QListWidget, QListView {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    padding: 4px;
    border-radius: 6px;
}}
QListWidget::item:hover {{
    background-color: {c["bg_card"]};
}}
QListWidget::item:selected {{
    background-color: {c["accent"]};
    color: white;
}}

/* === Разделители === */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {c["border"]};
    background-color: {c["border"]};
    max-height: 1px;
    max-width: 1px;
}}

/* === Скроллбар === */
QScrollBar:vertical {{
    background-color: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: {c["scrollbar"]};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {c["scrollbar_hover"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background-color: transparent;
    height: 6px;
}}
QScrollBar::handle:horizontal {{
    background-color: {c["scrollbar"]};
    border-radius: 3px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {c["scrollbar_hover"]};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* === Tooltip === */
QToolTip {{
    background-color: {c["bg_surface"]};
    color: {c["text_primary"]};
    border: 1px solid {c["border"]};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}}

/* === Диалоги === */
QDialog {{
    background-color: {c["bg_window"]};
}}

/* === Группа === */
QGroupBox {{
    border: 1px solid {c["border"]};
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px 8px 8px 8px;
    color: {c["text_secondary"]};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}}

/* === Спинбокс === */
QSpinBox {{
    background-color: {c["bg_input"]};
    color: {c["text_primary"]};
    border: 1px solid {c["border"]};
    border-radius: 6px;
    padding: 5px 8px;
}}
QSpinBox:focus {{
    border-color: {c["border_focus"]};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background-color: transparent;
    border: none;
    width: 16px;
}}

/* === Меню === */
QMenu {{
    background-color: {c["bg_surface"]};
    color: {c["text_primary"]};
    border: 1px solid {c["border"]};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 20px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {c["accent"]};
    color: white;
}}
QMenu::separator {{
    height: 1px;
    background-color: {c["border"]};
    margin: 3px 8px;
}}
"""


_THEMES: dict[Theme, str] = {
    Theme.DARK: _make_stylesheet(_DARK),
    Theme.LIGHT: _make_stylesheet(_LIGHT),
}

# Цвета для прямого использования
_COLORS: dict[Theme, dict] = {
    Theme.DARK: _DARK,
    Theme.LIGHT: _LIGHT,
}

_CURRENT_THEME = Theme.DARK


def apply_theme(theme: Theme) -> None:
    """Применяет тему к приложению.

    Args:
        theme: Темная или светлая тема.
    """
    global _CURRENT_THEME
    _CURRENT_THEME = theme
    app = QApplication.instance()
    if app:
        app.setStyleSheet(_THEMES[theme])

    # Устанавливаем шрифт
    try:
        from pathlib import Path
        import os
        import sys

        root = Path(__file__).parent.parent.parent.parent
        font_dir = root / "resources" / "fonts"

        from PySide6.QtGui import QFontDatabase

        for font_file in font_dir.glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(font_file))

        if app:
            font = app.font()
            font.setFamily("Noto Sans")
            font.setPointSize(10)
            app.setFont(font)
    except Exception:
        pass


def get_color(key: str, theme: Theme | None = None) -> str:
    """Возвращает цвет по ключу для текущей (или указанной) темы.

    Args:
        key: Ключ цвета (например "accent", "bg_card").
        theme: Тема или None для текущей.

    Returns:
        Цвет в hex.
    """
    t = theme or _CURRENT_THEME
    return _COLORS[t].get(key, "#ffffff")


def current_theme() -> Theme:
    """Возвращает текущую активную тему."""
    return _CURRENT_THEME
