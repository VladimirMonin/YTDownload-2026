---
applyTo: "build/**"
name: "BuildSystemInstructions"
description: "Правила сборки приложения под Windows"
---

# 🛠️ Build System

**Stack:** UV + PyInstaller 6+ (onedir) + Inno Setup 6+

**Обфускации нет.** PyArmor не используется.

---

## Команды

```powershell
# Установка зависимостей
uv sync

# Запуск приложения
uv run python app.py

# Сборка через PyInstaller
uv run pyinstaller build/ytdownloader.spec

# Тесты
uv run pytest tests/ -v
```

---

## Pipeline сборки

```
UV venv → PyInstaller (onedir) → Inno Setup
```

---

## Структура build/

```
build/
├── build.py           # Скрипт сборки
├── ytdownloader.spec  # PyInstaller config (onedir)
└── setup.iss          # Inno Setup config
```

---

## Добавление зависимости

1. Добавь в `pyproject.toml` → `dependencies`
2. Проверь лицензию: MIT/BSD/Apache → OK, **GPL → ЗАПРЕЩЕНО!**
3. Обнови `THIRD_PARTY_NOTICES.txt`
4. Если data files → добавь в `.spec` → `datas`

---

## LGPL Compliance (КРИТИЧНО!)

- **Только `onedir`** (не `onefile`) — DLL должны быть заменяемы
- PySide6 (LGPLv3) → `_internal/PySide6/`
- FFmpeg (LGPLv3) → `vendor/ffmpeg/bin/`
- Лицензии → `licenses/` + `THIRD_PARTY_NOTICES.txt`

**Разрешённые лицензии:** MIT, BSD, Apache 2.0, ISC, LGPL, PSF, OFL  
**Запрещённые:** GPL, AGPL, Proprietary

---

## data_files (spec)

```python
datas = [
    ("resources/fonts", "resources/fonts"),
    ("resources/icons", "resources/icons"),
    ("vendor/ffmpeg/bin", "vendor/ffmpeg/bin"),
]
```

---

**Конец Build System Instructions**
