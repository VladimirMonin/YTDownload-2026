"""Виджет настроек загрузки: качество, тип, субтитры.

Классы:
    DownloadOptionsWidget: Компактные опции для конкретной загрузки.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from ...domain.models import AppSettings
from ...domain.models.app_settings import DownloadType, QualityOption


class DownloadOptionsWidget(QWidget):
    """Компактная строка опций загрузки.

    Signals:
        options_changed(): Пользователь изменил опции.
    """

    options_changed = Signal()

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui(settings)
        self._connect_signals()

    def _init_ui(self, settings: AppSettings) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Качество
        layout.addWidget(QLabel(self.tr("Качество:")))
        self._quality_combo = QComboBox()
        for opt in QualityOption:
            self._quality_combo.addItem(opt.display_name(), opt)
        self._set_combo(self._quality_combo, settings.quality)
        self._quality_combo.setMinimumWidth(120)
        layout.addWidget(self._quality_combo)

        # Тип
        layout.addWidget(QLabel(self.tr("Тип:")))
        self._type_combo = QComboBox()
        self._type_combo.addItem(self.tr("Видео + аудио"), DownloadType.VIDEO)
        self._type_combo.addItem(self.tr("Только аудио"), DownloadType.AUDIO)
        self._set_combo(self._type_combo, settings.download_type)
        layout.addWidget(self._type_combo)

        # Субтитры
        self._subs_check = QCheckBox(self.tr("Субтитры"))
        self._subs_check.setChecked(settings.save_subtitles)
        layout.addWidget(self._subs_check)

        # Язык субтитров
        self._lang_combo = QComboBox()
        for lang_code, lang_name in [
            ("ru", "RU"),
            ("en", "EN"),
            ("kk", "KK"),
            ("de", "DE"),
            ("fr", "FR"),
            ("es", "ES"),
            ("uk", "UK"),
            ("zh", "ZH"),
            ("ja", "JA"),
        ]:
            self._lang_combo.addItem(lang_name, lang_code)
        self._set_combo_by_data(self._lang_combo, settings.subtitle_lang)
        self._lang_combo.setMinimumWidth(60)
        self._lang_combo.setEnabled(settings.save_subtitles)
        layout.addWidget(self._lang_combo)

        # Описание
        self._desc_check = QCheckBox(self.tr("Описание"))
        self._desc_check.setChecked(settings.save_description)
        layout.addWidget(self._desc_check)

        # Обложка
        self._thumb_check = QCheckBox(self.tr("Обложка"))
        self._thumb_check.setChecked(settings.save_thumbnail)
        layout.addWidget(self._thumb_check)

        layout.addStretch()

    def _connect_signals(self) -> None:
        self._quality_combo.currentIndexChanged.connect(self.options_changed)
        self._type_combo.currentIndexChanged.connect(self.options_changed)
        self._subs_check.toggled.connect(self._on_subs_toggled)
        self._subs_check.toggled.connect(self.options_changed)
        self._lang_combo.currentIndexChanged.connect(self.options_changed)
        self._desc_check.toggled.connect(self.options_changed)
        self._thumb_check.toggled.connect(self.options_changed)

    def _on_subs_toggled(self, checked: bool) -> None:
        self._lang_combo.setEnabled(checked)

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

    def apply_settings(self, settings: AppSettings) -> None:
        """Применяет настройки из AppSettings."""
        self._set_combo(self._quality_combo, settings.quality)
        self._set_combo(self._type_combo, settings.download_type)
        self._subs_check.setChecked(settings.save_subtitles)
        self._set_combo_by_data(self._lang_combo, settings.subtitle_lang)
        self._desc_check.setChecked(settings.save_description)
        self._thumb_check.setChecked(settings.save_thumbnail)

    @property
    def quality(self) -> QualityOption:
        """Выбранное качество."""
        return QualityOption(self._quality_combo.currentData())

    @property
    def download_type(self) -> DownloadType:
        """Выбранный тип загрузки."""
        return DownloadType(self._type_combo.currentData())

    @property
    def save_subtitles(self) -> bool:
        return self._subs_check.isChecked()

    @property
    def subtitle_lang(self) -> str:
        return self._lang_combo.currentData()

    @property
    def save_description(self) -> bool:
        return self._desc_check.isChecked()

    @property
    def save_thumbnail(self) -> bool:
        return self._thumb_check.isChecked()
