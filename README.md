# 🎬 YTDownload 2026

CLI, прямой Python API и MCP для загрузки видео и плейлистов; существующая настольная оболочка сохраняется.

**Стек:** Python 3.12+ · PySide6 · yt-dlp · FFmpeg · UV · FastMCP

Разработка: [AGENTS.md](AGENTS.md), [инженерная документация](docs/engineering.md),
[философия command-first](docs/foundation/project-philosophy.md). Исходный GUI
сохраняется. Независимо приняты S1–S6 и конечный command-first переход в согласованной
offline-границе: runtime/storage, cooperative cancellation, truthful outcomes,
task-ID attribution, ограниченное удаление, реальные adapters/lifetime и CI isolation.
S5-R1 закрыт. Actual CI preparation/argv/env проверены на local Windows/Python3.14.2;
hosted CI/Linux/Python3.12/pwsh7, live/codec, native Trash и EXE/manual visual
не квалифицированы:
[план](docs/command-first/PLAN.md),
[предлагаемый контракт](docs/command-first/CONTRACT.md),
[фактическая проверка и ограничения](docs/command-first/VERIFICATION.md).

Q1 независимо технически принят: устранены first-party type/lint findings без
ослабления правил; mypy0/68, configured Ruff0 по 106 Python files, offline291.
Это проверенный source-срез, не готовность консольного EXE. Следующий Q2 должен
отдельно подтвердить нашу CLI-сборку и полную командную функциональность, а не
только запуск/help. GUI build/visual в эту работу не входят; live-проверка требует
конкретного разрешённого пользовательского URL.

---

## ✨ Возможности

| Функция | Описание |
|---------|----------|
| 📥 Загрузка видео и плейлистов | Best / 1080p / 720p / 480p / Audio Only |
| 🎵 Audio Only | Извлечение аудиодорожки в .m4a через FFmpeg |
| 📝 Субтитры | Скачивание .vtt/.srt (с выбором языка) |
| 🖼️ Обложка | Сохранённая thumbnail, формат по факту |
| 📄 Описание | Sidecar `.description`, если сохранён |
| 📁 Структура папок | `OutDir/download-<task_id>/PlaylistName/001 - Title/Title.ext` |
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
# Default endpoint: http://127.0.0.1:8765/mcp после подписок/восстановления окна
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
protocol boundary, но не tool-effect E2E или загрузка. Отдельные S5 integration
cases проверяют standalone lifetime и useful tool effects. Детали — [CLI/MCP/GUI](docs/agent-instructions/04-mcp-and-gui.md).

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

Standalone `queue add` flush-ит acceptance, затем ждёт реальный итог: exit0 —
только done+persisted, failure/cancel/unsaved — exit1 со safe stderr error, без
второго stdout JSON. Встроенный `cli.main(..., services=...)` возвращает acceptance
без wait/close чужого runtime. History queries/preview — readonly snapshot без
lease/recovery/write. `--data-dir` выбирает профиль, не подключение к GUI;
standalone `queue cancel` отказывает OWNER_REQUIRED до создания пустой очереди.
GUI и embedded HTTP используют один owner; disconnect клиента не отменяет Job.
Entry закрывает admission, transport/bridges и действительно join-ит runtime.

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
| `delete_download(id, delete_files?, confirm?, plan_token?)` | Preview → согласие → тот же ID/режим/token; exact files или history-only |

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
Smokes выделяют ещё более узкий owned subtree; synthetic файлы сохраняются.
Discovery cleanup не заменяет отдельные active-job/entry lifetime proofs S5.
Общая библиотека не означает общую живую очередь разных процессов.

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
output_dir/                         # Выбранный root; default home/Downloads/YTDownloader
├── download-42/                    # ID одной принятой задачи-плейлиста
│   └── PlaylistName/
│       ├── 001 - VideoTitle/
│       │   ├── VideoTitle.mp4      # Пример media; фактическое расширение зависит от результата
│       │   ├── VideoTitle.info.json
│       │   ├── VideoTitle.description
│       │   ├── VideoTitle.webp     # Если thumbnail сохранён
│       │   └── VideoTitle.ru.vtt   # Если subtitles сохранены
│       └── 002 - OtherTitle/
│           └── ...
└── download-43/                    # Другой task, даже если title совпадает
    └── VideoTitle/
        ├── VideoTitle.mp4
        └── ...
```

---

Новые результаты реального yt-dlp backend размещаются под `download-<task_id>`:
разные admissions не присваивают друг другу одноимённые файлы. Старые files/history
не перемещаются; доверяйте возвращённым `artifact_paths`/legacy path fields, не
вычисляйте принадлежность по названию или newest folder. Это не разрешение удаления
всего дерева и не координация общего output между отдельными profiles.

## 🏗️ Архитектура

CLI, MCP и existing GUI managers вызывают один Application API; независимое
application/domain ядро не импортирует Qt, CLI parser или MCP SDK. Canonical MCP
factory живёт в infrastructure, принимает существующий API и не создаёт другую
очередь. [PLAN](docs/command-first/PLAN.md) сохраняет исходные причины/целевые owners,
[VERIFICATION](docs/command-first/VERIFICATION.md) — текущую ограниченную приёмку.

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
uv run --locked --no-sync ruff check --config pyproject.toml <first-party-python-files>
uv run --locked --no-sync ruff check --select E,F,I <changed-python-files>
```

Оба placeholders заменяются реальными непустыми массивами отдельных путей.
Configured gate сохраняет E/F/I/UP и проверяет весь согласованный first-party
scope, включая root entrypoints, build helper, src/scripts/tests и новые файлы.
Правило формирования finite manifest и исключения только неизменного imported
PFK — в [quality gates](docs/agent-instructions/05-quality-gates.md).

Для принятого Q1 independently verified: **mypy exit0/68**, **configured Ruff
exit0/106**, **changed E/F/I exit0/31**, **291 passed/7 e2e deselected/0 skipped**
и четыре module smokes exit0. Исходные 34 mypy и 57 Ruff findings S6, дополнительный
build I001 (58 в полном исходном first-party gate Q1) и прежние RED сохранены;
они не переписаны в исторический PASS. Imported checker/recursive whole-root Ruff —
NOT_RUN. Эти числа относятся к frozen Q1, не к непринятым параллельным Q2 edits.
Подробности — [VERIFICATION](docs/command-first/VERIFICATION.md). Live E2E требует
отдельного разрешения и конкретного URL; примеры руководства его не дают.
Prose-only finish требует final-byte doc checks, не повторения принятого suite/type/lint.

---

### CI и локальная граница проверки

Существующий [workflow](.github/workflows/ci.yml) сохраняет push-to-main/PR triggers,
Linux/Windows matrix и прежнюю установку зависимостей/FFmpeg. Это процедура для
подготовленных CI runners, не разрешение агенту запускать installers или `uv sync`.
После provisioning отдельный Python step создаёт новый owned subtree в RUNNER_TEMP
и назначает profile/home/temp/cache/log roots **до** collection/children. В offline
фазе используются locked/no-sync, явный audited Qt plugin, исключение
`tests/downloads` и четыре module-form smokes. `YTDL_OUTPUT_DIR` не является
продуктовым override: default output следует synthetic home, tests могут передать
явные settings. Детали — [тестирование](.github/instructions/testing.instructions.md).
S6 independently ACCEPTED: actual preparation и пять последующих workflow commands
прошли на local Windows/Python3.14.2, включая useful API/JSON/physical default
output/readonly CLI/next writer и275-case suite. Это не Linux/Python3.12/GitHub
hosted/pwsh7 qualification. Фактические executions/reuse/NOT_RUN — в VERIFICATION;
публикация и наблюдённые remote jobs не выводятся из local PASS.

## Прямой Python API и время жизни

`src.bootstrap.create_runtime` собирает независимое приложение без окна/сервера и
глобальной настройки logging. `main.initialize_app()` сохраняет прежний dict keys
и aliases `application_api`/`command_api`, добавляя owning `runtime`.

Пример **чтения собственного тестового профиля**, не рабочего пользовательского store.
До запуска назначьте YTDL_DATA_DIR и остальные isolation roots только своему
тестовому дереву по инструкции тестирования; отсутствие env здесь не скрывается
fallback-ом в личный профиль:

```python
import os
from pathlib import Path
from src.bootstrap import create_runtime

profile = Path(os.environ["YTDL_DATA_DIR"]).resolve()
with create_runtime(profile, read_only=True) as runtime:
    summaries = runtime.api.list_downloads()
```

Read-only создаёт detached last-saved snapshot, не папку/lease/executor/recovery и
не подключение к чужой живой очереди. Writable runtime сначала берёт exclusive lease
на canonical root; второй writer получает OWNER_BUSY. При writable reopen orphan
queued/downloading/merging становятся failed/INTERRUPTED без replay/очистки media.
Закрывайте принадлежащий caller-у runtime: context manager делает drain;
`close(cancel=False, wait=True)` ждёт принятое, `cancel=True` запрашивает cooperative
stop. `wait=False` не означает closed и удерживает lease до реального join.
Borrowed wrapper не закрывает caller. Standalone adapter lifetime/read-only CLI
и `--data-dir` проверены в S5; отдельные процессы с одной библиотекой не разделяют
live queue. MainWindow/HTTP handle только заимствуют runtime, desktop/server entry
владеет окончательным close. Ошибка или неполный cleanup даёт nonzero, не ложный closed.

В S3 `queue_add_download` возвращает принятие, не файл. `get_task` и
`wait_for_download(id, timeout=...)` дают detached snapshots; timeout прекращает
ожидание, не Job. `cancel_requested` — intent; running task становится cancelled
только после quiescence управляемого backend. Независимая ошибка остаётся failed,
а done требует подтверждённого media и сохранения. Known partial files не удаляются.
При terminal save failure live snapshot содержит PERSISTENCE_FAILED,
result_persisted=False и известные paths, readonly reader — лишь last-saved JSON.
Даже `closed=True` требует проверки `error_codes`/`persistence_error_ids`.
Нет hard stop deadline, Undo или media+JSON transaction.

List/search накладывают live facts до selection/limit и маппят ту же captured пару;
результат может устареть после capture, но не менять статус после фильтрации.
Unknown progress/speed/eta — None; измеренный0 остаётся0. Settings целиком фиксируются
при admission: update не меняет A/B; новый pool cap применяется только после drain
старой очереди/futures/callbacks, без двух работающих поколений.

`get_settings()` возвращает копию; `update_settings()` сохраняет до публикации
новых defaults. Overrides при construction сами по себе не записываются. JSON
ошибки не превращаются в defaults/успех: STORAGE_CORRUPT/PERSISTENCE_FAILED/OWNER_BUSY
доступны в API и safe transport mapping; unexpected exceptions не раскрывают raw text. Политика и
границы — [CONTRACT](docs/command-first/CONTRACT.md), [окружение](docs/agent-instructions/02-environment-and-dependencies.md).

## Ограниченное удаление через Application API

В S4 удаление требует явного плана: сначала `prepare_delete_download(id,
delete_files=...)`, затем после согласия — `delete_download` с теми же id/режимом
и `expected_plan=preview.plan_token`. Предпросмотр ничего не перемещает и не
меняет историю; boolean confirm и сам token не удостоверяют человека. Без token
API возвращает CONFIRMATION_REQUIRED, изменившийся план — STALE_PLAN. После отказа
или потерянного ответа нужны новый preview и новое согласие, не автоматический retry.

`delete_files=False` удаляет только запись истории. Файловый режим переносит только
явно записанные media/sidecar paths в системную Корзину: ни каталоги, ни parent,
ни unlisted/sibling files не удаляются. Одна папка в старой записи не доказывает
принадлежность файлов (UNSAFE_FILE_SCOPE); доступен keep-files. Небезопасные roots,
links/junction ancestry, shared paths и незавершённая работа в той же области
блокируют эффект. Cancel intent ещё не разрешает удалять активную задачу.

При частичном переносе или ошибке сохранения истории возвращается структурированный
PARTIAL_DELETE/PERSISTENCE_FAILED: известные moved/missing/failed/unknown counts,
`history_deleted` и `recovery=repreview`. Уже перемещённые bytes не откатываются;
запись не считается удалённой без подтверждённого save. `files_removed=True` означает
хотя бы один известный перенос, а не исчезновение папки; при нуле переносов — False.

Default adapter — lazy QtCore Trash без QApplication и без permanent-delete fallback.
Независимо проверены восстановимые synthetic OS-edge moves, реальная policy/JSON и
installed capability; **native Trash move/restore остаётся NOT_RUN**, не гарантия
восстановления на каждом OS/volume. Media+JSON не crash-atomic transaction.

В S5 CLI `--plan-token`, MCP `plan_token` и существующий GUI modal передают
matching plan; legacy repository-delete fallback удалён. GUI готовит оба режима
до диалога: No сохраняет данные, Yes использует выбранный token, изменение во
время modal безопасно отказывает. Пример ручного history-only workflow:

```bash
uv run --locked --no-sync python -m src.interfaces.cli --json history delete 42 --keep-files --preview
uv run --locked --no-sync python -m src.interfaces.cli --json history delete 42 --keep-files --confirm --plan-token TOKEN_FROM_PREVIEW
```

Вторую команду выполняют только после просмотра результата и согласия. Token не
удостоверяет человека; после partial/lost response нужно новое подтверждение.
Общая legacy/native Qt privacy не заявлена. Подробнее — [руководство](docs/README.md#6-история-загрузок) и
[принятый scope/ограничения](docs/command-first/VERIFICATION.md).

## 🔧 Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `YTDL_DATA_DIR` | APPDATA/YTDownloader либо home/YTDownloader | Непустой data-root override; явный Python `data_root` выше env. Под ним config/data/logs; handlers настраиваются отдельно. Smoke всегда переопределяет его в собственный subtree и восстанавливает после проверки |
| `YTDL_LOG_LEVEL` | `INFO` | Уровень логирования (`DEBUG`/`INFO`/`WARNING`); DEBUG не разрешает пользовательское содержимое |
| `YTDL_LOG_DIR` | Entry: выбранный data root/logs; readonly CLI без override — stderr | Непустой override GUI/CLI contexts. GUI fallback: YTDL_DATA_DIR → APPDATA/home. Legacy setup_logging без аргумента сохраняет fallback project/logs; entry contexts закрывают только acquired handlers, сохраняя caller objects |
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
