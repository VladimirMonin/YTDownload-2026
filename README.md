# 🎬 YTDownload 2026

Настольный загрузчик YouTube видео и плейлистов с MCP-сервером для AI-агентов.

**Стек:** Python 3.12+ · PySide6 · yt-dlp · FFmpeg · UV · FastMCP

Разработка: [AGENTS.md](AGENTS.md), [инженерная документация](docs/engineering.md),
[философия command-first](docs/foundation/project-philosophy.md). Исходный GUI
сохраняется. Независимо приняты S1 (isolated baseline) и S2 (runtime/ports,
владение хранилищем, fail-closed JSON и smoke isolation). S3–S6 ещё
не реализованы/не приняты: [план](docs/command-first/PLAN.md),
[предлагаемый контракт](docs/command-first/CONTRACT.md),
[фактическая проверка и ограничения](docs/command-first/VERIFICATION.md).

---

## ✨ Возможности

| Функция | Описание |
|---------|----------|
| 📥 Загрузка видео и плейлистов | Best / 1080p / 720p / 480p / Audio Only |
| 🎵 Audio Only | Извлечение аудиодорожки в .m4a через FFmpeg |
| 📝 Субтитры | Скачивание .vtt/.srt (с выбором языка) |
| 🖼️ Обложка | Загрузка thumbnail .webp |
| 📄 Описание | Сохранение description.txt |
| 📁 Структура папок | `OutDir/PlaylistName/001 - Title/video.mp4 + ...` |
| 🕒 История | JSON-база всех загрузок с поиском |
| 🌙 Dark / Light тема | Переключение в один клик |
| ⚙️ Настройки | Папка, прокси, качество, язык субтитров |
| 🤖 MCP сервер | 10 инструментов для AI-агентов |

---

## 🚀 Быстрый старт

Ниже — первоначальная установка **пользователем**, не разрешение агенту запускать
installers/скачивание/`uv sync`. В существующем окружении разработка и диагностика
используют `.venv`, `uv run --locked --no-sync` и [правила изоляции](.github/instructions/testing.instructions.md).

### 1. Установка UV

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Через pip (универсально):**

```bash
pip install uv
```

### 2. Клонирование и запуск

```bash
git clone <repo-url> ytdownload-2026
cd ytdownload-2026

# Установить зависимости
uv sync

# Запустить приложение из готового окружения
uv run --locked --no-sync python app.py
```

> **FFmpeg** нужен для слияния видео+аудио в .mp4.  
> Linux/macOS: приложение ищет `ffmpeg`, `ffprobe`, `ffplay` в системном `PATH` — обычно достаточно установить пакет `ffmpeg`.  
> Windows: положите `ffmpeg.exe`, `ffprobe.exe`, `ffplay.exe` в `vendor/ffmpeg/bin/`.  
> Явный путь к ffmpeg можно задать через `YTDL_FFMPEG_PATH`.

---

## 🐛 Запуск в режиме DEBUG

Дважды кликните `run_debug.bat` — откроется окно с полными логами.  
Окно **не схлопнется** при ошибке/закрытии приложения.

```
YT Downloader  [DEBUG MODE]
Все логи уровня DEBUG и выше выводятся в консоль
```

---

## 🤖 MCP Сервер

YTDownload 2026 поднимает HTTP MCP-сервер при запуске GUI.  
AI-агенты (Claude, Cursor, VS Code Copilot, Cline) могут управлять загрузками через 10 инструментов.

**Запуск MCP вместе с приложением:**

```bash
uv run --locked --no-sync python app.py
# MCP доступен на http://127.0.0.1:8765/mcp сразу после старта
```

**Автономный запуск MCP сервера (HTTP, без GUI):**

```bash
uv run --locked --no-sync python -m src.infrastructure.mcp.server --host 127.0.0.1 --port 8765
```

**Канонический stdio entrypoint для Hermes и других command-based MCP клиентов:**

```bash
uv run --locked --no-sync python -m src.interfaces.cli server stdio
```

Совместимый wrapper `uv run --locked --no-sync python mcp_stdio_server.py` сохранён
для старых скриптов и делегирует в тот же модуль. Прежняя запись
`uv run python -m src.interfaces.cli server stdio` обозначает тот же канонический
путь; для проверки готового окружения используйте locked/no-sync вариант выше.

**Offline stdio MCP parity smoke:**

```bash
uv run --locked --no-sync python -m scripts.smoke_mcp_stdio
```

После назначения собственных synthetic roots реальный MCP client запускает текущий
interpreter `-m scripts.smoke_mcp_stdio --serve`; child вызывает настоящий CLI
`main(["server", "stdio"], services=...)` и finally joins свой legacy coordinator.
Проверяются discovery parity и cleanup receipt с timeout. Это реальный stdio
protocol boundary, но не tool-effect E2E, не загрузка и не доказательство lifetime
неизменённого standalone CLI. Детали — [CLI/MCP/GUI](docs/agent-instructions/04-mcp-and-gui.md).

### Unified CLI / MCP contract

Один и тот же application/command layer лежит под CLI и MCP. Канонические
входные точки:

```bash
uv run --locked --no-sync python -m src.interfaces.cli --help
uv run --locked --no-sync python -m src.interfaces.cli queue add <url> --quality 720p
uv run --locked --no-sync python -m src.interfaces.cli history list --format json
uv run --locked --no-sync python -m src.interfaces.cli server http --host 127.0.0.1 --port 8765
uv run --locked --no-sync python -m src.interfaces.cli server stdio
```

Offline validation для этого контракта:

```bash
uv run --locked --no-sync python -m scripts.smoke_cli_help
uv run --locked --no-sync python -m scripts.smoke_mcp
uv run --locked --no-sync python -m scripts.smoke_mcp_stdio
```

Эти smoke-проверки доказывают help/registration/discovery parity и не подменяют
реальные destructive или сетевые сценарии.

### Инструменты MCP

| Инструмент | Описание |
|------------|----------|
| `list_downloads(status?, limit?)` | Список всех загрузок с фильтром по статусу |
| `get_download(id)` | Полные детали загрузки + все пути к файлам |
| `search_downloads(query, limit?)` | Поиск по названию и URL |
| `search_with_description(query, limit?)` | Поиск + текст описания из файла |
| `get_file_paths(id)` | Абсолютные пути: video, audio, subtitles, thumbnail |
| `get_transcript(id, lang?, raw?)` | Читает субтитры/транскрипцию (.vtt/.srt) |
| `read_description(id)` | Текст .description файла ролика |
| `add_download(url, quality?, ...)` | Добавить URL в очередь загрузки |
| `cancel_download(id, confirm?)` | Отмена активной загрузки (двухфазная) |
| `delete_download(id, delete_files?, confirm?)` | Удаление из истории + файлы с диска |

Канонический source of truth для имён/count живёт в
`src/infrastructure/mcp/manifest.py`; `scripts/mcp_expected_tools.py`,
`scripts/smoke_mcp.py`, `scripts/smoke_mcp_stdio.py` и регрессионные тесты
читают тот же manifest, чтобы не было drift между docs/help и реестром.

### Что именно проверяют smoke-скрипты

- `uv run --locked --no-sync python -m scripts.smoke_cli_help` — пять help cases, не выполнение команд загрузки.
- `uv run --locked --no-sync python -m scripts.smoke_mcp` — регистрация/discovery ожидаемых 10 инструментов; HTTP не запускается.
- `uv run --locked --no-sync python -m src.interfaces.cli server stdio` — действующий canonical server entrypoint, сам по себе не smoke и не доказанный S1 runtime shutdown.
- `uv run --locked --no-sync python -m scripts.smoke_mcp_stdio` — настоящий client/child protocol discovery с изоляцией и cleanup, не tool effects.
- `uv run --locked --no-sync python -m scripts.smoke_gui` — offscreen window/show/events/close, не полный интерактивный workflow и не HTTP lifecycle `app.py`.

Выполнять из корня после [pre-process isolation](.github/instructions/testing.instructions.md).
Smokes выделяют ещё более узкий owned subtree; synthetic файлы сохраняются. Их
временный private executor cleanup не заменяет будущий public ApplicationRuntime.
Общая библиотека также не означает общую живую очередь разных процессов.

### Opt-in real validation gates

Следующие проверки остаются отдельным явным gate и не считаются закрытыми одними
offline smoke-скриптами:

- реальный `queue add` / `add_download` против YouTube URL;
- реальный `queue cancel` / `cancel_download` на живой queued/downloading задаче;
- sidecar-артефакты (`.description`, `.info.json`, subtitle files, thumbnail) на
  реальной загрузке;
- stdio tool invocation через unified path в реальном клиентском сценарии с
  живыми эффектами, а не только discovery parity.

### Конфигурация клиентов

#### Claude Desktop

Откройте `claude_desktop_config.json` (`%APPDATA%\Claude\claude_desktop_config.json` на Windows):

```json
{
  "mcpServers": {
    "ytdownload-2026": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://127.0.0.1:8765/mcp"]
    }
  }
}
```

> `npx mcp-remote` автоматически конвертирует HTTP → stdio.  
> Требует Node.js. Установить: [nodejs.org](https://nodejs.org/).

#### VS Code Copilot

Добавьте в `.vscode/mcp.json` в корне проекта:

```json
{
  "servers": {
    "ytdownload-2026": {
      "type": "http",
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

#### Cursor

Настройки → MCP → Add Server:

```json
{
  "ytdownload-2026": {
    "type": "http",
    "url": "http://127.0.0.1:8765/mcp"
  }
}
```

#### Cline / Chatbox

```json
{
  "mcpServers": {
    "ytdownload-2026": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

#### Проверка через MCP Inspector

```bash
npx @modelcontextprotocol/inspector http://127.0.0.1:8765/mcp
```

Откроется веб-UI для тестирования всех инструментов в браузере.

---

## 📂 Структура загрузок

```
output_dir/                         # Настраивается в Settings
├── PlaylistName/                   # Для плейлистов
│   ├── 001 - VideoTitle/
│   │   ├── 001 - VideoTitle.mp4   # Смонтированное видео
│   │   ├── 001 - VideoTitle.info.json
│   │   ├── 001 - VideoTitle.description
│   │   ├── 001 - VideoTitle.webp  # Thumbnail
│   │   └── 001 - VideoTitle.ru.vtt  # Субтитры
│   └── 002 - VideoTitle/
│       └── ...
└── VideoTitle/                     # Для одиночных видео
    ├── VideoTitle.mp4
    └── ...
```

---

## 🏗️ Архитектура

Ниже — направление разделения ответственности, не заявление о завершённой
независимости ядра. Существующие обходы API и целевые owners описаны в [PLAN](docs/command-first/PLAN.md).

```
┌─────────────────────────────────────────────────────┐
│ UI: PySide6 Widgets · Qt Signals · Thread-safe      │
├─────────────────────────────────────────────────────┤
│ Application: DownloadCoordinator · ThreadPoolExec   │
├─────────────────────────────────────────────────────┤
│ Domain: Pure Python · Protocols · EventBus          │
├─────────────────────────────────────────────────────┤
│ Infrastructure: yt-dlp · FFmpeg · JSON repos · MCP  │
└─────────────────────────────────────────────────────┘
```

**Ключевые принципы:**

- **Clean Architecture** — слои не знают о соседях сверху
- **Protocol-based DI** — зависимости через ABC/Protocol
- **Thread-safe signals** — Qt Signal Bridge из EventBus  
- **MCP в отдельном thread** — asyncio не блокирует Qt event loop
- **Repository port** — хранение отделяется интерфейсом; миграция в SQLite/PeeWee не входит в текущую задачу и не проверена.

---

## 🛠️ Разработка

В готовой `.venv`, после назначения собственных home/storage/temp/cache/log roots
**до collection/import** по [инструкции тестирования](.github/instructions/testing.instructions.md):

```bash
uv run --locked --no-sync pytest tests/ -m "not e2e" -q
uv run --locked --no-sync mypy src/ --ignore-missing-imports
uv run --locked --no-sync ruff check --select E,F,I <changed-python-files>
```

Подставить непустой список изменённых Python-файлов. Полный lint/type baseline
не равен changed-file gate: после S2 mypy остаётся exit1 с 34 унаследованными ошибками/15 файлами;
подробности — [VERIFICATION](docs/command-first/VERIFICATION.md). Live E2E требует
отдельного явного разрешения с конкретным URL; примеры в руководстве его не дают.
Изменения только документации требуют affected checks, не автоматического повторения suite.

---

## Прямой Python API и время жизни

`src.bootstrap.create_runtime` собирает независимое приложение без окна/сервера и
глобальной настройки logging. `main.initialize_app()` сохраняет прежний dict keys
и aliases `application_api`/`command_api`, добавляя owning `runtime`.

Пример **чтения собственного тестового профиля**, не рабочего пользовательского store:

```python
from pathlib import Path
from src.bootstrap import create_runtime

with create_runtime(Path("owned-test-profile"), read_only=True) as runtime:
    summaries = runtime.api.list_downloads()
```

Read-only создаёт detached last-saved snapshot, не папку/lease/executor/recovery и
не подключение к чужой живой очереди. Writable runtime сначала берёт exclusive lease
на canonical root; второй writer получает OWNER_BUSY. При writable reopen orphan
queued/downloading/merging становятся failed/INTERRUPTED без replay/очистки media.
Закрывайте принадлежащий caller-у runtime: context manager делает drain; явный S2
join — `close(cancel=False, wait=True)`. `wait=False` не освобождает lease до join.
Borrowed wrapper не закрывает caller. Полная cooperative cancellation/outcome модель
ещё S3, standalone adapter lifetime/read-only CLI mode — S5; `--data-dir` пока не
добавлен в parser. Отдельные процессы с одной библиотекой не разделяют live queue.

`get_settings()` возвращает копию; `update_settings()` сохраняет до публикации
новых defaults. Overrides при construction сами по себе не записываются. JSON
ошибки не превращаются в defaults/успех: STORAGE_CORRUPT/PERSISTENCE_FAILED/OWNER_BUSY
доступны в direct API exceptions; полное transport mapping ещё впереди. Политика и
границы — [CONTRACT](docs/command-first/CONTRACT.md), [окружение](docs/agent-instructions/02-environment-and-dependencies.md).

## 🔧 Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `YTDL_DATA_DIR` | APPDATA/YTDownloader либо home/YTDownloader | Непустой data-root override; явный Python `data_root` выше env. Под ним config/data/logs; handlers настраиваются отдельно. Smoke всегда переопределяет его в собственный subtree и восстанавливает после проверки |
| `YTDL_LOG_LEVEL` | `INFO` | Уровень логирования (`DEBUG`/`INFO`/`WARNING`); DEBUG не разрешает пользовательское содержимое |
| `YTDL_LOG_DIR` | `logs/` рядом с проектом | Непустой override для `setup_logging()` без аргумента; явный `log_dir` выше env. GUI `app.py` передаёт свой APPDATA log path |
| `YTDL_FFMPEG_PATH` | auto-detect | Явный путь к исполняемому `ffmpeg`; без него используется `vendor/ffmpeg/bin` или системный `PATH` |
| `YTDL_FFPROBE_PATH` | auto-detect | Явный путь к `ffprobe` для тестов и диагностики |
| `YTDL_FFPLAY_PATH` | auto-detect | Явный путь к `ffplay` для тестов и диагностики |

---

## 📄 Лицензии третьих сторон

| Компонент | Лицензия | Путь |
|-----------|----------|------|
| FFmpeg | LGPL 2.1 | `vendor/ffmpeg/LICENSE.txt` |
| Tabler Icons | MIT | `resources/icons/tabler/LICENSE` |
| JetBrains Mono | OFL 1.1 | `resources/fonts/OFL.txt` |
| NotoSans | OFL 1.1 | `resources/fonts/OFL.txt` |
| Project Foundation Kit 0.3.0 | MIT, включая donor notices ECC/UIZZE | [LICENSE](tools/project-foundation/LICENSE), [UPSTREAM](tools/project-foundation/UPSTREAM.md), [notices](tools/project-foundation/THIRD_PARTY_NOTICES.md) |
