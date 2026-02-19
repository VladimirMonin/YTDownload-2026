---
applyTo: "app.py,main.py"
name: "EntryPointsInstructions"
description: "Архитектура entry points и DI Container"
---

# 🚀 Entry Points

---

## 📁 Файлы

| Файл      | Роль                                         |
| --------- | -------------------------------------------- |
| `app.py`  | Thin entry (logging → QApplication → window) |
| `main.py` | DI Container (`initialize_app()`)            |

---

## 🏗️ Ответственность

### main.py — DI Container

```python
def initialize_app() -> dict:
    settings_repo = SettingsRepository()
    settings = settings_repo.load()
    history_repo = JsonHistoryRepository(settings.output_dir)
    download_service = YtDlpService(settings)
    coordinator = DownloadCoordinator(download_service, history_repo, settings)
    return {
        "settings_repo": settings_repo,
        "history_repo": history_repo,
        "download_service": download_service,
        "coordinator": coordinator,
    }
```

### app.py — Thin Entry

```python
setup_logging()
app = QApplication(sys.argv)
services = initialize_app()
window = MainWindow(services)
window.show()
sys.exit(app.exec())
```

---

## ➕ Добавление сервиса

```python
# 1. main.py → initialize_app()
new_svc = NewService(dep1, dep2)
return { ..., "new_svc": new_svc }

# 2. app.py → lifecycle (если нужен start/stop)
services["new_svc"].start()
app.aboutToQuit.connect(services["new_svc"].stop)
```

---

## ⚠️ Антипаттерн

```python
# ❌ Создание сервиса прямо в app.py
service = MyService(...)

# ✅ Только через DI Container
services = initialize_app()
services["my_service"].start()
```

---

**Конец Entry Points Instructions**
