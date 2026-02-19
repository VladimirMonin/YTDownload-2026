---
applyTo: "src/ui/**"
name: "QtSignalsThreadingInstructions"
description: "Правила работы с Qt Signals и потоками в PySide6"
---

# 🧵 Qt Signals & Threading - Agent Instructions

**Проект использует PySide6**

---

## ⚠️ КРИТИЧЕСКОЕ ПРАВИЛО: UI обновления только из Main Thread!

```python
# ❌ CRASH — вызывается из worker thread
def _on_storage_saved(self, data):
    self.model.refresh()

# ✅ Signal автоматически маршализует в main thread
class MyWidget(QWidget):
    _refresh_signal = Signal()
    def __init__(self):
        self._refresh_signal.connect(self._do_refresh)
        event_bus.subscribe("storage_saved", self._on_event)
    def _on_event(self, data):
        self._refresh_signal.emit()  # Thread-safe!
    def _do_refresh(self):
        self.model.refresh()  # Main thread ✅
```

---

## 📚 EventBus vs Qt Signals

|                  | EventBus                       | Qt Signals         |
| ---------------- | ------------------------------ | ------------------ |
| Thread-safe UI   | ❌ Callback в потоке publisher | ✅ Auto-marshaling |
| Где использовать | domain/application             | UI layer only      |
| Зависимость      | Pure Python                    | Требует QObject    |

**Паттерн Signal Bridge** (реализован в `StatusBridge`):

```python
# EventBus (worker thread) → Qt Signal → Main Thread slot
class StatusBridge(QObject):
    _update_signal = Signal(object, object)
    def __init__(self, event_bus):
        self._update_signal.connect(self._apply_update)
        event_bus.subscribe("status_display_changed", self._on_event)
    def _on_event(self, data):      # worker thread
        self._update_signal.emit(data["info"], data["custom_text"])
    def _apply_update(self, info, text):  # main thread ✅
        self._label.setStatusInfo(info, text)
```

---

## 🚫 Запрещённые паттерны

```python
# ❌ QTimer.singleShot из worker thread — НЕ РАБОТАЕТ
QTimer.singleShot(0, self.model.refresh)

# ❌ Прямое обращение к UI из worker
self.parent_window.label.setText(result.text)  # CRASH!
```

**Замена:** Используй Qt Signal или StatusBridge.

---

## 📋 Checklist для агентов

- [ ] EventBus callback обновляет UI? → Signal Bridge
- [ ] Код в domain/application? → EventBus, НЕ Qt Signals
- [ ] QRunnable/QThread обновляет UI? → Signals inner class
- [ ] Cleanup в closeEvent? → `event_bus.unsubscribe()`

---

## 🎯 Best Practices

1. Internal signals с префиксом `_`: `_refresh_signal = Signal()`
2. Typed Signals: `finished = Signal(dict)`, НЕ `Signal()`
3. Отписывайся в `cleanup()` или `closeEvent`

---

**Конец Qt Signals & Threading Instructions**
