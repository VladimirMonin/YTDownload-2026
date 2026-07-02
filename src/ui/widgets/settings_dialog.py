"""Диалог настроек приложения.

Классы:
    SettingsDialog: Полный диалог редактирования AppSettings.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ...domain.models import AppSettings
from ...domain.models.app_settings import DownloadType, QualityOption
from ..utils.tabler_icons import TablerIcons, get_icon


class SettingsDialog(QDialog):
    """Диалог редактирования настроек.

    Signals:
        settings_saved(settings): Пользователь сохранил настройки.
    """

    settings_saved = Signal(AppSettings)

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle(self.tr("Настройки"))
        self.setMinimumWidth(480)
        self.setMinimumHeight(400)
        self._init_ui()
        self._populate(settings)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(16)

        # ── Папка загрузки ─────────────────────────────────────
        download_group = QGroupBox(self.tr("Загрузки"))
        download_form = QFormLayout(download_group)
        download_form.setSpacing(10)

        dir_row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText(self.tr("Папка для сохранения…"))
        dir_row.addWidget(self._dir_edit, 1)
        browse_btn = QPushButton()
        browse_btn.setObjectName("icon_btn")
        browse_btn.setIcon(get_icon(TablerIcons.FOLDER_OPEN, size=16))
        browse_btn.setFixedSize(32, 32)
        browse_btn.clicked.connect(self._on_browse)
        dir_row.addWidget(browse_btn)
        download_form.addRow(self.tr("Папка:"), dir_row)

        # Качество по умолчанию
        self._quality_combo = QComboBox()
        for opt in QualityOption:
            self._quality_combo.addItem(opt.display_name(), opt)
        download_form.addRow(self.tr("Качество:"), self._quality_combo)

        # Тип по умолчанию
        self._type_combo = QComboBox()
        self._type_combo.addItem(self.tr("Видео + аудио"), DownloadType.VIDEO)
        self._type_combo.addItem(self.tr("Только аудио"), DownloadType.AUDIO)
        download_form.addRow(self.tr("Тип:"), self._type_combo)

        # Параллельность
        self._concurrent_spin = QSpinBox()
        self._concurrent_spin.setRange(1, 8)
        self._concurrent_spin.setSuffix(self.tr(" потоков"))
        download_form.addRow(self.tr("Параллельно:"), self._concurrent_spin)

        layout.addWidget(download_group)

        # ── Субтитры и доп. файлы ─────────────────────────────
        files_group = QGroupBox(self.tr("Дополнительные файлы"))
        files_form = QFormLayout(files_group)
        files_form.setSpacing(8)

        self._subs_check = QCheckBox(self.tr("Сохранять субтитры"))
        files_form.addRow(self._subs_check)

        # Язык субтитров
        self._lang_combo = QComboBox()
        for code, name in [
            ("ru", "Русский"),
            ("en", "English"),
            ("kk", "Қазақ"),
            ("uk", "Українська"),
            ("de", "Deutsch"),
            ("fr", "Français"),
            ("es", "Español"),
            ("zh", "中文"),
            ("ja", "日本語"),
        ]:
            self._lang_combo.addItem(name, code)
        files_form.addRow(self.tr("Язык субтитров:"), self._lang_combo)

        self._desc_check = QCheckBox(self.tr("Сохранять описание"))
        files_form.addRow(self._desc_check)

        self._thumb_check = QCheckBox(self.tr("Сохранять обложку"))
        files_form.addRow(self._thumb_check)

        layout.addWidget(files_group)

        # ── Прокси ────────────────────────────────────────────
        proxy_group = QGroupBox(self.tr("Прокси"))
        proxy_form = QFormLayout(proxy_group)
        proxy_form.setSpacing(8)

        self._proxy_edit = QLineEdit()
        self._proxy_edit.setPlaceholderText("socks5://127.0.0.1:7890")
        proxy_form.addRow(self.tr("Прокси:"), self._proxy_edit)

        proxy_hint = QLabel(self.tr("Форматы: socks5://host:port · http://user:pass@host:port"))
        proxy_hint.setObjectName("secondary")
        proxy_form.addRow(proxy_hint)

        layout.addWidget(proxy_group)
        # ── MCP сервер ────────────────────────────────────────────
        mcp_group = QGroupBox(self.tr("MCP сервер"))
        mcp_form = QFormLayout(mcp_group)
        mcp_form.setSpacing(8)

        self._mcp_port_spin = QSpinBox()
        self._mcp_port_spin.setRange(1024, 65535)
        self._mcp_port_spin.setToolTip(
            self.tr("Порт для MCP сервера (по умолчанию 8765). Изменение требует перезапуска.")
        )
        mcp_form.addRow(self.tr("Порт:"), self._mcp_port_spin)

        mcp_hint = QLabel(self.tr("Изменение порта вступит в силу после перезапуска приложения"))
        mcp_hint.setObjectName("secondary")
        mcp_form.addRow(mcp_hint)

        layout.addWidget(mcp_group)
        # ── Интерфейс ─────────────────────────────────────────
        ui_group = QGroupBox(self.tr("Интерфейс"))
        ui_form = QFormLayout(ui_group)

        self._theme_combo = QComboBox()
        self._theme_combo.addItem(self.tr("Тёмная"), "dark")
        self._theme_combo.addItem(self.tr("Светлая"), "light")
        ui_form.addRow(self.tr("Тема:"), self._theme_combo)

        layout.addWidget(ui_group)

        # ── Кнопки ────────────────────────────────────────────
        layout.addStretch()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, s: AppSettings) -> None:
        """Заполняет поля из объекта настроек."""
        self._dir_edit.setText(str(s.output_dir))
        self._set_combo(self._quality_combo, s.quality)
        self._set_combo(self._type_combo, s.download_type)
        self._concurrent_spin.setValue(s.max_concurrent)
        self._subs_check.setChecked(s.save_subtitles)
        self._set_combo_by_data(self._lang_combo, s.subtitle_lang)
        self._desc_check.setChecked(s.save_description)
        self._thumb_check.setChecked(s.save_thumbnail)
        self._proxy_edit.setText(s.proxy)
        self._mcp_port_spin.setValue(s.mcp_port)
        self._set_combo_by_data(self._theme_combo, s.theme)

    def _on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, self.tr("Выберите папку"), self._dir_edit.text()
        )
        if folder:
            self._dir_edit.setText(folder)

    def _on_save(self) -> None:
        # Валидация proxy
        proxy_text = self._proxy_edit.text().strip()
        if proxy_text and not self._validate_proxy(proxy_text):
            QMessageBox.warning(
                self,
                self.tr("Некорректный прокси"),
                self.tr(
                    "Формат прокси не распознан.\n"
                    "Ожидается: socks5://host:port или http://[user:pass@]host:port\n\n"
                    "Настройки будут сохранены, но прокси может не работать."
                ),
            )

        settings = AppSettings(
            output_dir=Path(self._dir_edit.text().strip() or str(Path.home() / "Downloads")),
            quality=self._quality_combo.currentData(),
            download_type=self._type_combo.currentData(),
            max_concurrent=self._concurrent_spin.value(),
            save_subtitles=self._subs_check.isChecked(),
            subtitle_lang=self._lang_combo.currentData(),
            save_description=self._desc_check.isChecked(),
            save_thumbnail=self._thumb_check.isChecked(),
            proxy=proxy_text,
            mcp_port=self._mcp_port_spin.value(),
            theme=self._theme_combo.currentData(),
        )
        self.settings_saved.emit(settings)
        self.accept()

    @staticmethod
    def _validate_proxy(proxy: str) -> bool:
        """Проверяет формат прокси-строки.

        Args:
            proxy: Строка прокси.

        Returns:
            True если формат распознан.
        """
        import re

        pattern = re.compile(
            r"^(socks[45]|https?|socks5h)://"  # схема
            r"([^:@]+:[^:@]+@)?"  # опциональный user:pass@
            r"[\w.\-]+"  # host
            r"(:\d{1,5})?$",  # опциональный :port
            re.IGNORECASE,
        )
        return bool(pattern.match(proxy))

    @staticmethod
    def _set_combo(combo: QComboBox, value: object) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    @staticmethod
    def _set_combo_by_data(combo: QComboBox, data: object) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == data:
                combo.setCurrentIndex(i)
                return
