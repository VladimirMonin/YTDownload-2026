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
| 🤖 MCP сервер | 9 инструментов для AI-агентов |

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
> Положите `ffmpeg.exe`, `ffprobe.exe`, `ffplay.exe` в `vendor/ffmpeg/bin/`.  
> Скачать: [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) или [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds/releases).

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

YTDownload 2026 поднимает MCP-сервер при запуске.  
AI-агенты (Claude, Cursor, VS Code Copilot, Cline) могут управлять загрузками через 9 инструментов.

**Запуск MCP вместе с приложением:**

```bash
uv run python app.py
# MCP доступен на http://127.0.0.1:8765/mcp сразу после старта
```

**Автономный запуск MCP сервера (без GUI):**

```bash
uv run python -m src.infrastructure.mcp.server --host 127.0.0.1 --port 8765
```

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

#### Cline / Chatbox (SSE transport)

```json
{
  "mcpServers": {
    "ytdownload-2026": {
      "type": "sse",
      "url": "http://127.0.0.1:8765/sse"
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
| `YTDL_FFMPEG_PATH` | `vendor/ffmpeg/bin/ffmpeg.exe` | Путь к ffmpeg.exe |

---

## 📄 Лицензии третьих сторон

| Компонент | Лицензия | Путь |
|-----------|----------|------|
| FFmpeg | LGPL 2.1 | `vendor/ffmpeg/LICENSE.txt` |
| Tabler Icons | MIT | `resources/icons/tabler/LICENSE` |
| JetBrains Mono | OFL 1.1 | `resources/fonts/OFL.txt` |
| NotoSans | OFL 1.1 | `resources/fonts/OFL.txt` |
