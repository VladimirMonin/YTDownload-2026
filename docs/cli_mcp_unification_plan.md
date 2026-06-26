# План унификации общей логики для CLI и MCP

Статус: инженерный план, без реализации

## 1. Короткий вывод

Единым источником правды должен стать application-слой use case'ов: отдельные команды и запросы, работающие поверх `DownloadCoordinator`, `IHistoryRepository`, `ISettingsRepository`, `YtDlpService` и сериализаторов ответа.

CLI и MCP должны стать тонкими адаптерами над этим слоем:
- CLI отвечает только за парсинг аргументов, help, exit codes и формат вывода;
- MCP отвечает только за schema/docstring/tool registration и преобразование ошибок в JSON-ответ;
- GUI остаётся отдельным входом, но по возможности тоже должна вызывать те же use case'ы, а не дублировать файловые и history-операции в `MainWindow`.

Иными словами: не `MCP reuse CLI` и не `CLI reuse MCP`, а оба reuse одного прикладного API.

## 2. Карта текущих точек входа

### GUI

1. `app.py`
   - поднимает логирование;
   - создаёт `QApplication`;
   - вызывает `initialize_app()`;
   - стартует HTTP MCP thread через `run_server(...)`;
   - создаёт `MainWindow(services)`.

2. `src/ui/main_window.py`
   - orchestrator для виджетов и менеджеров;
   - через `DownloadManager` вызывает `DownloadCoordinator.add/cancel`;
   - через `HistoryManager` читает/удаляет историю;
   - местами содержит прикладные/file-system операции напрямую (`_on_history_delete`, `_open_folder`, локальная логика refresh/search wiring).

3. `src/ui/managers/download_manager.py`
   - уже тонкий bridge `EventBus -> Qt Signals`;
   - по сути UI-адаптер над `DownloadCoordinator`.

4. `src/ui/managers/history_manager.py`
   - тонкий sync-адаптер над `IHistoryRepository`;
   - возвращает `get_all/search/delete`, но без общего query/command слоя.

### CLI

Сейчас полноценного пользовательского CLI для доменных операций нет.

Текущие CLI entry points фактически такие:
- `uv run python app.py` — запуск GUI;
- `uv run python -m src.infrastructure.mcp.server --host ... --port ...` — HTTP MCP server;
- `uv run python mcp_stdio_server.py` — stdio MCP server;
- `uv run python scripts/smoke_mcp.py` — offline discovery smoke;
- `uv run python scripts/smoke_mcp_stdio.py` — stdio parity smoke;
- `uv run python scripts/smoke_gui.py` — GUI init smoke.

Вывод: CLI как transport существует только для запуска серверов/смоков, но не как первый-class интерфейс к истории, очереди и чтению артефактов.

### MCP

1. `src/infrastructure/mcp/server.py`
   - `create_mcp_server(services)` — регистрация FastMCP tools;
   - `run_server(...)` — HTTP transport;
   - `__main__` с `argparse` — отдельный transport bootstrap.

2. `mcp_stdio_server.py`
   - повторно вызывает `initialize_app()`;
   - повторно строит MCP через `create_mcp_server(services)`;
   - запускает stdio transport.

3. `src/infrastructure/mcp/tools/*.py`
   - каждый tool напрямую читает `history_repo` или вызывает `coordinator`;
   - часть общей логики уже вынесена в `_utils.py` (нормализация enum/date, serializer short/full);
   - но прикладная логика всё ещё размазана по transport-модулям.

## 3. Где логика уже общая, а где смешана с transport/UI

### Уже общая

1. `main.py::initialize_app()`
   - единая сборка dependency graph.

2. `src/application/download_coordinator.py`
   - очередь;
   - статусы;
   - история задач;
   - publish событий;
   - orchestration yt-dlp + FFmpeg.

3. `src/infrastructure/ytdlp_service.py`
   - download/fetch_info;
   - format selection;
   - output scanning;
   - ffmpeg wiring.

4. `src/infrastructure/repositories.py`
   - единый persistence слой для history/settings.

5. `src/infrastructure/mcp/tools/_utils.py`
   - единая сериализация `HistoryEntry -> dict` для части MCP tools.

### Смешано с transport/UI

1. `src/infrastructure/mcp/tools/add_download.py`
   - transport-level validation смешана с прикладным вызовом;
   - mapping строк -> enum живёт внутри MCP tool, а не в общем command-слое.

2. `src/infrastructure/mcp/tools/search_downloads.py`
   - query logic и подгрузка description живут прямо в MCP transport;
   - это будущий кандидат в общий query service.

3. `src/infrastructure/mcp/tools/get_transcript.py`
   - file reading + subtitle cleanup + timestamps formatting живут в MCP tool;
   - это прикладной read-use-case, а не MCP-специфика.

4. `src/infrastructure/mcp/tools/delete_download.py`
   - двухфазная preview semantics — transport-специфична и может остаться в адаптере;
   - но resolve-folder / count-files / remove-history-entry / delete-files лучше вынести в общее command API.

5. `src/ui/main_window.py::_on_history_delete`
   - GUI напрямую делает `shutil.rmtree(...)` и потом `history_manager.delete(...)`;
   - то есть удаление истории уже реализовано вторым путём, отдельно от MCP.

6. `src/ui/widgets/history_widget.py::_on_search`
   - UI-фильтр делает substring search локально по уже загруженным entries;
   - репозиторий умеет `search(query)` отдельно;
   - semantics поиска между интерфейсами уже различаются.

7. bootstrap transport'ов
   - HTTP transport bootstrap в `src/infrastructure/mcp/server.py`;
   - stdio transport bootstrap в `mcp_stdio_server.py`;
   - оба повторяют `initialize_app() + create_mcp_server(...)` схему.

8. MCP tool registry drift
   - `search_with_description(...)` существует в `search_downloads.py`,
   - отражён в `scripts/mcp_expected_tools.py` и docs,
   - но в `src/infrastructure/mcp/tools/__init__.py` лог пишет `count=9`, а сама регистрация устроена вручную и является точкой риска drift.

## 4. Целевая схема слоёв

Рекомендуемая схема:

1. `src/domain/`
   - модели, enum'ы, protocol'ы.
   - без transport concerns.

2. `src/application/use_cases/`
   - единый источник правды для CLI и MCP.
   - разделить на:
     - `commands/` — side effects;
     - `queries/` — read-only операции.

3. `src/application/dto/` или `src/application/serializers/`
   - transport-neutral response модели/DTO;
   - например `DownloadSummary`, `DownloadDetails`, `TranscriptResult`, `DeletePreview`.

4. `src/interfaces/cli/`
   - parser/help/output/exit codes;
   - вызывает use case'ы;
   - не читает repo/service напрямую.

5. `src/interfaces/mcp/` или текущий `src/infrastructure/mcp/`
   - tool registration;
   - schema/docstrings;
   - unwrap аргументов и вызов use case'ов;
   - JSON envelopes ошибок/preview confirmation.

6. `src/ui/`
   - вызывает те же commands/queries хотя бы для history delete/search/open-path metadata;
   - Qt-specific состояние и сигналы остаются здесь.

## 5. Какая именно часть должна стать единым источником правды

Единым источником правды должен стать новый прикладной API примерно такого уровня:

- `queue_add_download(...)`
- `queue_cancel_download(...)`
- `history_list_downloads(...)`
- `history_get_download(...)`
- `history_search_downloads(...)`
- `history_search_with_description(...)`
- `history_get_file_paths(...)`
- `history_get_transcript(...)`
- `history_read_description(...)`
- `history_prepare_delete(...)`
- `history_delete(...)`

Это не обязательно публичный Python API в одном файле; важно, чтобы именно этот слой:
- валидировал и нормализовал входы;
- преобразовывал enum/string/path/date к transport-neutral DTO;
- принимал решения о том, что значит preview/delete/search/transcript;
- был одинаково вызываем из CLI и MCP.

`DownloadCoordinator` оставлять как низкоуровневый orchestration engine очереди, а не превращать в универсальный фасад для всех read/delete/report операций.

## 6. Будущие команды CLI и методы MCP

### CLI

Нужен один корневой вход, например:

`uv run python -m src.interfaces.cli`

или позже console script из `pyproject.toml`, например `ytdl`.

Предлагаемая структура help:

1. `ytdl queue add <url>`
   - флаги: `--quality`, `--type`, `--subtitle-lang`, `--save-subtitles`, `--save-description`, `--save-thumbnail`
   - вывод: `task_id`, `status`

2. `ytdl queue cancel <id>`
   - флаги: `--confirm`
   - по умолчанию preview/пояснение не нужен, можно сразу отменять как обычную CLI-команду
   - если нужен safety parity с MCP, можно добавить `--preview`

3. `ytdl history list`
   - флаги: `--status`, `--limit`, `--format json|table`

4. `ytdl history get <id>`
   - флаги: `--format json|pretty`

5. `ytdl history search <query>`
   - флаги: `--limit`, `--with-description`, `--format json|table`

6. `ytdl history transcript <id>`
   - флаги: `--lang`, `--raw`, `--timestamps`

7. `ytdl history description <id>`
   - без сложных флагов, максимум `--format json|text`

8. `ytdl history delete <id>`
   - флаги: `--delete-files/--keep-files`, `--confirm`, `--preview`

9. `ytdl server http`
   - флаги: `--host`, `--port`

10. `ytdl server stdio`
   - без аргументов или с минимальными debug-флагами.

Принцип help для CLI:
- примеры в стиле текущих MCP docstring;
- одинаковые имена аргументов с MCP, где это возможно;
- `--format json` как режим машинного потребления;
- ненулевой exit code на hard-failure.

### MCP

MCP-имена лучше сохранить совместимыми с уже опубликованными tools:
- `add_download`
- `cancel_download`
- `delete_download`
- `list_downloads`
- `get_download`
- `search_downloads`
- `search_with_description`
- `get_file_paths`
- `get_transcript`
- `read_description`

Что должно измениться внутри MCP:
- tool вызывает use case, а не repo/coordinator напрямую;
- transport адаптирует двухфазные confirm/preview ответы в JSON;
- docstring остаётся transport-specific, но фактическая логика ответа берётся из общего слоя.

## 7. Какие части должны остаться transport-specific

### Должны остаться в CLI

- argparse/typer/click wiring;
- help и examples;
- табличный/plain/json вывод;
- exit codes;
- shell-friendly флаги и короткие aliases.

### Должны остаться в MCP

- `@mcp.tool()` регистрация;
- большие agent-facing docstrings;
- JSON envelopes вида `{error, hint}`;
- mandatory two-phase confirmation semantics для destructive tools.

### Должны остаться в GUI

- Qt signal wiring;
- открытие папки через `os.startfile/open/xdg-open`;
- layout/state/visual feedback;
- локальная фильтрация уже загруженного списка как UX-оптимизация, если она поверх общего query, а не вместо него.

## 8. Пошаговый план маленькими слайсами

1. Ввести transport-neutral DTO и общий serializer слой
   - вынести из MCP `_utils.py` в application/dto или serializers;
   - закрыть short/full/download/file-paths/date/enum нормализацию.

2. Ввести read-only query layer
   - `list/get/search/search_with_description/get_transcript/read_description/get_file_paths`;
   - MCP tools перевести на него без изменения публичных имён.

3. Ввести command layer для destructive/history ops
   - `prepare_delete`, `delete`, `cancel_download`, позже `add_download` normalization;
   - GUI удалить прямой `shutil.rmtree(...)` из `MainWindow` и перевести на тот же command.

4. Ввести единый command/query фасад для bootstrap
   - `build_application_api(services)` или аналог;
   - чтобы CLI/MCP/UI не собирали use case graph вручную по-разному.

5. Добавить первый-class CLI для history/queue
   - сначала только read commands и `queue add/cancel`;
   - формат вывода `json` + человекочитаемый table.

6. Свести transport bootstrap
   - один модуль server bootstrap для `http`/`stdio`;
   - `mcp_stdio_server.py` превращается в тонкий wrapper или исчезает в пользу `ytdl server stdio`.

7. Убрать registry drift
   - единый список MCP tool specs или auto-registration manifest;
   - smoke/tests/docs читают один и тот же manifest, а не держат count/name в нескольких местах.

8. Довести GUI до reuse общей логики там, где это безопасно
   - delete history;
   - search semantics;
   - file-path resolution/preview metadata.

9. После стабилизации — подумать об отдельном application API для real-download diagnostics
   - не смешивать operational smoke/e2e scripts с пользовательским CLI.

## 9. Главные риски

### Очередь загрузок

Риск:
- при слишком раннем выносе можно сломать thread ownership, cancellation и event emission.

Что беречь:
- `DownloadCoordinator` должен остаться владельцем executor/futures/active services.
- новый слой не должен обходить coordinator и напрямую трогать `_history_repo` там, где важен lifecycle task.

### История

Риск:
- разные интерфейсы начнут по-разному трактовать search/delete/output_dir/file paths.

Что делать:
- search semantics описать один раз в query layer;
- folder resolution вынести в общий helper/use case;
- GUI/MCP/CLI перестают держать собственные копии этого решения.

### События

Риск:
- общий command layer начнёт публиковать события напрямую и дублировать coordinator/UI flows.

Что делать:
- события очереди остаются обязанностью coordinator;
- queries не публикуют события вообще;
- history delete command публикует события только если реально нужен cross-interface refresh contract.

### Форматы ответов

Риск:
- CLI захочет table/plain text, MCP — строгий dict/list, GUI — объекты моделей;
- при неправильном слое DTO получится либо MCP-shaped ядро, либо UI-shaped ядро.

Что делать:
- в общем слое возвращать DTO/dataclass/plain dict neutral-shape;
- адаптеры уже сами оформляют table/json/tool envelope.

### Побочные файлы

Риск:
- transcript/description/delete operations работают с реальными файлами и могут разойтись в path rules.

Что делать:
- path resolution, existence checks, truncation limits и language selection вынести в общий read/delete слой;
- transport оставляет только presentation.

## 10. Что можно проверить офлайн, а что потребует реального прогона

### Можно проверить офлайн

1. CLI help/argparse smoke.
2. MCP tool discovery parity.
3. Совпадение списка tool names между manifest/docs/smoke.
4. Query/use-case unit tests на JSON history fixtures.
5. Transcript parsing/cleanup/timestamps на локальных `.vtt/.srt` fixtures.
6. Delete preview logic на временных папках.
7. GUI history delete/search wiring без реального YouTube.
8. HTTP vs stdio bootstrap parity.

### Потребует реального прогона

1. Реальная загрузка через `yt-dlp` после перехода `add_download`/queue command на новый слой.
2. Отмена активной реальной загрузки.
3. Проверка, что sidecar artifacts (`.info.json`, subtitles, description, thumbnail`) по-прежнему доходят до истории и потом читаются через CLI/MCP.
4. Проверка, что stdio MCP клиент реально вызывает tools через новый путь, а не только discoverability.

## 11. Практическая рекомендация по порядку

Лучший первый рефакторинг — не `add_download`, а read-only операции:
- `list_downloads`
- `get_download`
- `get_file_paths`
- `search_downloads`
- `search_with_description`
- `read_description`
- `get_transcript`

Почему:
- меньше риск сломать очередь;
- быстрее появляется общий слой для CLI;
- можно сделать почти весь слайс offline.

Второй слайс — delete/cancel.
Третий — add_download normalization и затем первый настоящий пользовательский CLI.

## 12. Итог в одной фразе

Нужно строить не общий transport, а общий прикладной API use case'ов; CLI и MCP должны стать тонкими адаптерами над ним, а GUI — постепенно перестать держать собственные версии history/file/delete логики.
