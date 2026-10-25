---
applyTo: "build/**"
name: "BuildSystemInstructions"
description: "Правила сборки приложения под Windows"
---

# 🛠️ Build System

**Stack:** UV + PyInstaller 6+ (onedir) + Inno Setup 6+

**Обфускации нет.** PyArmor не используется.

---

## Автономная консоль Windows x64 (Q2)

`ytdl_cli.py` — тонкий absolute-import вход того же CLI. `build/ytdl_cli.spec`
строит **console=True onedir**, включая actual lazy yt-dlp extractors, metadata,
HTTP/stdio и dynamic MCP registrars из canonical manifest. Это не GUI build,
не onefile и не uv/Python-child shim. Прежние GUI spec/setup.iss/default route
сохранены; GUI EXE в Q2 не собирался и visual/manual проверка не запрашивается.

Только готовая `.venv`/уже установленный PyInstaller и existing admitted vendor
FFmpeg/FFprobe. Агент не выполняет sync/install/update/download. До build/imports
назначить все own isolation roots по [testing](testing.instructions.md). Из корня,
заменив примеры новыми собственными **absolute, внешними, непересекающимися** путями:

```powershell
uv run --locked --no-sync python build/build.py --target cli --work-dir 'C:\OwnedBuilds\q2-work-new' --dist-dir 'C:\OwnedBuilds\q2-artifact-new'
```

Оба пути должны отсутствовать. Helper отказывает existing/same/nested/relative/
checkout destinations, не делает clean/recursive delete/overwrite. CLI command
не передаёт --clean/--noconfirm. Не переиспользовать прежний кандидат; частичный
failed build сохраняется, не auto-pruned. Missing dependency/capability — blocker,
не разрешение скачать её. Без --target cli сохранён прежний GUI default.

Результат: root `artifact-manifest.json` и **полный** `YTDownloadCLI/` с `ytdl.exe`,
`_internal/`, separately replaceable `vendor/ffmpeg/bin/{ffmpeg.exe,ffprobe.exe}`,
licenses и THIRD_PARTY_NOTICES.txt. Frozen resolver ищет vendor рядом с resolved
реальным EXE, не cwd/_internal; source/env/explicit/platform/PATH priority сохранена.
Существующие component hashes/-version/-L/configuration и licenses фиксируются;
GPL/nonfree replacement не скачивается. PyInstaller Bootloader Exception отличается
от лицензии build tooling; local test не сертифицирует public redistribution.

Q2 ACCEPTED_Q2_LOCAL_OFFLINE для candidate-02:759 files/440588786 bytes, relocation
и полезная native CLI матрица/all11 leaves. EXE отдельно не является пакетом.
Полный Windows-friendly ZIP содержит ровно этот runtime и byte-identical manifest;
это новый контейнер, **не rebuild под будущим doc/commit SHA**. Build manifest
сохраняет actual accepted-prefix/source identities. После prose-only changes
не пересобирать и не повторять runtime gates. [README](../../README.md) отделяет
standalone use от source/Python-installed entry; [VERIFICATION](../../docs/command-first/VERIFICATION.md)
фиксирует71 native rows/8 complements, final-byte gates и URL/Trash/platform limits.

## Прежние GUI recipes (в Q2 не выполнялись)

Следующие пользовательские setup/GUI recipes сохранены для прежнего pipeline,
не являются разрешением агенту на uv sync/install/GUI build или сетевой pytest.
Агент в готовом окружении использует locked/no-sync и изоляцию/`not e2e` по
[канонической testing instruction](testing.instructions.md).

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
├── build.py           # GUI default / --target cli с new external roots
├── ytdl_cli.spec       # Standalone console onedir
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
