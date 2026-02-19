---
applyTo: "src/ui/**"
name: "GUIPatterns"
description: "Принципы разработки GUI — как сохранять MainWindow тонким"
---

# 🏗️ GUI Patterns — Thin Orchestrator

**Target:** MainWindow ≤ 400 строк | SettingsDialog ≤ 300 строк

---

## MainWindow — ТОЛЬКО:

1. UI Shell (`_init_ui`) + создание менеджеров
2. Signal Wiring (`_connect_signals`)
3. Config Sync (`_on_settings_changed` → все менеджеры)
4. Lifecycle (`show`, `closeEvent` → cleanup)

## MainWindow — НИКОГДА:

- ❌ Логика скачивания
- ❌ Прямые вызовы yt-dlp
- ❌ Storage вызовы
- ❌ Worker создание/управление (это в менеджерах)

---

## Менеджеры

| Менеджер          | Тип     | Ответственность                   |
| ----------------- | ------- | --------------------------------- |
| `DownloadManager` | QObject | Worker threads, прогресс, очередь |
| `HistoryManager`  | plain   | История загрузок, JSON            |

---

## QObject vs Plain class

- **QObject нужен:** EventBus callback обновляет UI (Signal Bridge)
- **Plain class:** всё остальное (синхронные вызовы)

---

## Добавление нового виджета

1. Создай `src/ui/widgets/my_widget.py`
2. Сигналы — публичные
3. Иконки — через `get_icon(TablerIcons.XXX)`
4. Тексты — через `self.tr("...")`
5. Метод `update_icons()` — обязателен

---

## Структура UI

```
┌──────────────────────────────────┐
│  Header: [Иконка + Название]     │
├──────────────────────────────────┤
│  URL Input + кнопка добавить     │
├──────────────────────────────────┤
│  Опции: Quality | Type | Subs   │
├──────────────────────────────────┤
│  Очередь загрузок               │
│  (список DownloadItemWidget)     │
├──────────────────────────────────┤
│  История (HistoryWidget)         │
└──────────────────────────────────┘
```

---

## Блок > 50 строк в MainWindow?

→ Extract в менеджер или виджет. Не раздувай orchestrator.

---

**Конец GUI Patterns**
