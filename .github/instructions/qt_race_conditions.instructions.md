---
applyTo: "src/ui/**"
name: "QtRaceConditions"
description: "Предотвращение Race Conditions в Qt Signals"
---

# 🏁 Race Conditions & Signal Order

---

## ⚠️ Порядок эмитов

```python
# ❌ Сигнал эмитится ДО изменения состояния
def activate(self, value, mode):
    self.widget.set_value(value)  # эмитит value_changed с mode="old"
    self.widget.set_mode(mode)    # поздно!

# ✅ Сначала состояние, потом триггер
def activate(self, value, mode):
    self.widget.set_mode(mode)
    self.widget.set_value(value)  # эмитит с mode="new"
```

---

## 🔄 Циклические сигналы

```python
# ❌ Бесконечный цикл
tab_changed → sync_layer → layer_changed → sync_tab → tab_changed...

# ✅ Решение 1: Early Return
def set_current_tab(self, index):
    if self.tabs.currentIndex() == index:
        return
    self.tabs.setCurrentIndex(index)

# ✅ Решение 2: Guard Flag
def set_value(self, value):
    if self._updating:
        return
    self._updating = True
    try:
        self._do_update(value)
    finally:
        self._updating = False

# ✅ Решение 3: blockSignals
self.widget.blockSignals(True)
self.widget.set_value(new_value)
self.widget.blockSignals(False)
self.trigger_update()  # явный триггер
```

---

## ⏱️ Debounce & Race Conditions

```python
# ❌ Debounce запоминает устаревшее состояние
def on_query_changed(self, query):
    layer = self.get_active_layer()  # текущий
    self._debounce_timer.start()
    # layer меняется до срабатывания debounce!

# ✅ Snapshot в момент триггера
def on_query_changed(self, query):
    self._pending_query = query
    self._pending_layer = self.get_active_layer()
    self._debounce_timer.start()

def execute_debounced(self):
    self.perform_search(self._pending_query, self._pending_layer)
```

---

## � P0: Search Mode layer→query (Episode 48)

```python
# ❌ set_query эмитит query_changed → debounce snapshot(layer=OLD)
panel.set_query(query)
panel.set_active_layer(layer)  # поздно!

# ✅ SearchModeCoordinator.activate() — СНАЧАЛА layer
panel.set_active_layer(layer)
panel.set_query(query)  # snapshot(layer=CORRECT)
```

---

## 📋 Checklist

- [ ] Сначала состояние, потом триггер?
- [ ] blockSignals при программной установке значений?
- [ ] Early return перед эмитом ("уже установлено")?
- [ ] Snapshot состояния до debounce/async?
- [ ] Защита от циклических сигналов?
- [ ] layer→query порядок в Search Mode?

---

**Конец Race Conditions Instructions**
