---
applyTo: "**"
name: "RunningApp"
description: "Правила запуска и тестирования приложения"
---

# 🚀 Running the App

## Запуск

```powershell
# Установка зависимостей (первый раз)
uv sync

# Запуск
uv run python app.py

# Тесты
uv run pytest tests/ -v -m "not e2e"

# E2E тесты (нужна сеть)
uv run pytest tests/ -v -m e2e

# Mypy
uv run mypy src/ --ignore-missing-imports

# Ruff
uv run ruff check src/ tests/
```

---

## Переменные окружения

| Переменная         | Описание                                 |
| ------------------ | ---------------------------------------- |
| `YTDL_LOG_LEVEL`   | DEBUG / INFO (по умолчанию INFO)         |
| `YTDL_FFMPEG_PATH` | Путь к ffmpeg.exe (по умолчанию vendor/) |

---

## Проверки перед коммитом

```powershell
# 1. Ruff (форматирование)
uv run ruff check src/ tests/

# 2. Mypy (типы)
uv run mypy src/ --ignore-missing-imports

# 3. Тесты (без e2e)
uv run pytest tests/ -m "not e2e" -v
```

---

**Конец Running App Instructions**
