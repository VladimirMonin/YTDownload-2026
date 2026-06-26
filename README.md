# 🎬 YTDownload 2026

Настольный загрузчик YouTube видео и плейлистов с MCP-сервером для AI-агентов.

**Стек:** Python 3.12+ · PySide6 · yt-dlp · FFmpeg · UV · FastMCP

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

# Запустить приложение
uv run python app.py
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
uv run python app.py
# MCP доступен на http://127.0.0.1:8765/mcp сразу после старта
```

**Автономный запуск MCP сервера (HTTP, без GUI):**

```bash
uv run python -m src.infrastructure.mcp.server --host 127.0.0.1 --port 8765
```

**Канонический stdio entrypoint для Hermes и других command-based MCP клиентов:**

```bash
uv run python -m src.interfaces.cli server stdio
```

Совместимый wrapper `uv run python mcp_stdio_server.py` сохранён для старых
скриптов, но просто делегирует в тот же `src.interfaces.cli server stdio` путь.

**Offline stdio MCP parity smoke:**

```bash
uv run python scripts/smoke_mcp_stdio.py
```

Скрипт поднимает `uv run python -m src.interfaces.cli server stdio` как реальный
stdio MCP server и проверяет, что набор инструментов discoverable и совпадает с
ожидаемым smoke-набором. Это именно `stdio MCP smoke / parity`, а не полный E2E
сценарий загрузки.

### Unified CLI / MCP contract

Один и тот же application/command layer лежит под CLI и MCP. Канонические
входные точки:

```bash
uv run python -m src.interfaces.cli --help
uv run python -m src.interfaces.cli queue add <url> --quality 720p
uv run python -m src.interfaces.cli history list --format json
uv run python -m src.interfaces.cli server http --host 127.0.0.1 --port 8765
uv run python -m src.interfaces.cli server stdio
```

Offline validation для этого контракта:

```bash
uv run python scripts/smoke_cli_help.py
uv run python scripts/smoke_mcp.py
uv run python scripts/smoke_mcp_stdio.py
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

- `uv run python scripts/smoke_cli_help.py` — offline CLI help smoke: проверяет корневой command tree, queue/history/server help и явные safety notes/примеры unified CLI surface.
- `uv run python scripts/smoke_mcp.py` — offline tool-discovery smoke: проверяет, что `create_mcp_server(initialize_app())` регистрирует ожидаемые 10 инструментов.
- `uv run python -m src.interfaces.cli server stdio` — канонический stdio entrypoint для Hermes/native MCP клиентов; совместимый `mcp_stdio_server.py` просто делегирует сюда.
- `uv run python scripts/smoke_mcp_stdio.py` — offline stdio parity smoke поверх реального stdio MCP client/server boundary; он проверяет discoverable tool set, но не является полноценной end-to-end проверкой stdio-сессии.
- `uv run python scripts/smoke_gui.py` — GUI initialization smoke; подтверждает инициализацию приложения, но не доказывает полный интерактивный GUI workflow.

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
- **Готово к SQLite** — `IHistoryRepository` легко заменяется на PeeWee

---

## 🛠️ Разработка

```bash
# Зависимости
uv sync

# Тесты (без E2E — без сети)
uv run pytest tests/ -m "not e2e" -v

# Тесты с реальными загрузками (нужна сеть)
uv run pytest tests/ -m e2e -v

# Проверка типов
uv run mypy src/ --ignore-missing-imports

# Линтер
uv run ruff check src/ tests/
```

---

## 🔧 Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `YTDL_LOG_LEVEL` | `INFO` | Уровень логирования (`DEBUG`/`INFO`/`WARNING`) |
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
