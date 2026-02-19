---
applyTo: "src/ui/**"
name: "UIIconsAndColors"
description: "Правила работы с иконками, кнопками и цветовыми схемами"
---

# 🎨 UI Icons & Colors - Agent Instructions

## 📦 Иконки: Tabler Icons

**Единственный источник:** `src/ui/utils/tabler_icons.py`

```python
from src.ui.utils import get_icon, get_pixmap, create_icon_label, TablerIcons

button.setIcon(get_icon(TablerIcons.SAVE, size=18))
label.setPixmap(get_pixmap(TablerIcons.MICROPHONE, size=16))
icon_label = create_icon_label(TablerIcons.CALENDAR, size=18)
```

---

## 🌗 Авто-цвет из темы

НЕ указывай цвет — он определяется автоматически!

```python
get_icon(TablerIcons.SAVE)              # ✅ цвет из palette
get_icon(TablerIcons.SAVE, color="#FFF") # ❌ хардкод
```

**Исключение:** Акцентные цвета (warning/success/error).

---

## 🔄 Обновление при смене темы

**Phase 11.0–11.1:** `ThemeController._update_theme_icons()` обновляет все виджеты.

Каждый виджет с иконками **ОБЯЗАН** иметь `update_icons()`:

```python
class MyTab(QWidget):
    def update_icons(self) -> None:
        """Вызывается из ThemeController._update_theme_icons()."""
        self.btn_save.setIcon(get_icon(TablerIcons.SAVE, size=18))
```

---

## 🌐 Локализация текстов

Все строки — через `self.tr()` или `_tr()` в tooltips:

```python
self.btn_save = QPushButton(self.tr("Сохранить"))  # ✅
self.btn_save = QPushButton("Сохранить")            # ❌
```

---

## 🎯 CSS: Только theme-aware цвета

```css
/* ✅ */
.text-secondary {
  opacity: 0.7;
}
/* ❌ */
.text-secondary {
  color: #6b7280;
}
```

---

## 📋 Checklist для нового виджета

- [ ] Иконки через `get_icon()` / `get_pixmap()`
- [ ] Есть метод `update_icons()`
- [ ] Тексты обёрнуты в `self.tr()`
- [ ] Нет хардкод цветов в CSS

---

**Конец UI Icons & Colors Instructions**
