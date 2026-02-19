# 🔌 MCP Server в PySide6-приложении — полный гайд

> Написано на основе реального опыта Whisper Voice Machine.
> Для агента, который ставит задачу с нуля.

---

## Что такое MCP и зачем он в Desktop-приложении

MCP (Model Context Protocol) — открытый протокол от Anthropic для подключения LLM-агентов к внешним источникам данных. Ты поднимаешь HTTP-сервер внутри своего приложения, и любой AI-клиент (Claude Desktop, Cursor, Cline, VS Code Copilot и др.) может вызывать твои инструменты как функции.

В GUI-приложении это означает: агент может **читать данные** из БД приложения и **управлять UI** — открывать окна, активировать вкладки, запускать поиск с подсветкой. Всё это через уже работающее приложение.

---

## Стек

```
FastMCP (mcp SDK)  — декларативная регистрация инструментов (@mcp.tool())
uvicorn            — ASGI HTTP-сервер
Starlette          — CORS + middleware
threading          — отдельный asyncio thread, не блокирует Qt main loop
EventBus           — bridge из asyncio thread → Qt Signal → UI
```

Зависимости: `mcp`, `uvicorn`, `starlette` (`uv add mcp uvicorn starlette`).

---

## Архитектура: почему отдельный thread

Qt main loop и asyncio event loop — несовместимы. Попытка запустить uvicorn в main thread заморозит UI навсегда.

**Правило:** MCP сервер живёт в `threading.Thread` со своим `asyncio.new_event_loop()`. Общение с UI — только через EventBus + Qt Signal bridge. Никаких прямых вызовов Qt-виджетов из обработчиков инструментов.

```
MCP Client
    │ HTTP
    ▼
uvicorn (asyncio loop в отдельном Thread)
    │ @mcp.tool() callback
    ▼
repository.search(...)  ← только I/O, без Qt!
    │ результат
    ▼
EventBus.emit("mcp_request_finished", {...})
    │ thread-safe
    ▼
Qt Signal bridge → UI update (main thread)
```

---

## Структура файлов

```
src/infrastructure/mcp/
├── server.py          # MCPServerManager: lifecycle start/stop, транспорты, middleware
└── tools/
    ├── __init__.py    # register_all_tools(), ToolCallbacks Protocol
    ├── search.py      # search_transcriptions
    ├── get_transcriptions.py
    ├── search_in_document.py
    ├── open_record.py     # единственный tool с доступом к EventBus (UI action)
    ├── user_notes.py      # read + update (Two-Phase Confirm)
    └── batch_operations.py
```

**Принцип SRP:** каждый инструмент — отдельный файл с функцией `create_<name>_tool(mcp, repository, config, callbacks)`. В `__init__.py` единственная точка регистрации — `register_all_tools()`.

---

## MCPConfig — доменный объект настроек

```python
@dataclass
class MCPToolsConfig:
    search_transcriptions: bool = True
    get_transcription_by_id: bool = True
    search_in_document: bool = True
    open_record: bool = True
    max_open_records: int = 10

@dataclass
class MCPConfig:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 7558
    sse_enabled: bool = True      # legacy SSE для Chatbox и Cline
    tools: MCPToolsConfig = field(default_factory=MCPToolsConfig)

    @property
    def server_url(self) -> str:
        return f"http://{self.host}:{self.port}/mcp"

    @property
    def sse_url(self) -> str:
        return f"http://{self.host}:{self.port}/sse"
```

`sse_enabled` — переключатель транспорта. Если `True` — поднимается Legacy SSE (`/sse` + `/messages`). Если `False` — только Streamable HTTP (`/mcp`). Подробнее о транспортах ниже.

---

## MCPServerManager — полный lifecycle

```python
class MCPServerManager:
    def __init__(self, config: MCPConfig, repository: IStorageRepository, event_bus: EventBus):
        self.config = config
        self.repository = repository
        self.event_bus = event_bus
        self._server_thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._uvicorn_server = None
        self._active_requests: int = 0
        self._is_running: bool = False
        self._mcp = None

        # Hot-reload при изменении настроек
        self.event_bus.subscribe("config_updated", self._on_config_changed)

    def start(self) -> bool:
        if self._is_running or not self.config.enabled:
            return False
        self.config.validate_port()  # ValueError если порт вне 1024-65535

        self._server_thread = threading.Thread(
            target=self._run_server_thread,
            name="MCPServerThread",
            daemon=True,  # ВАЖНО: daemon=True, иначе приложение не закроется
        )
        self._server_thread.start()

        # Ждём подтверждения запуска (максимум 5 секунд)
        for _ in range(50):
            if self._is_running:
                self.event_bus.emit("mcp_server_started", {"url": self.config.server_url})
                return True
            threading.Event().wait(0.1)
        return False

    def stop(self) -> None:
        if not self._is_running:
            return
        if self._loop and self._uvicorn_server:
            # Останавливаем из asyncio loop thread-safe способом
            self._loop.call_soon_threadsafe(
                setattr, self._uvicorn_server, "should_exit", True
            )
        if self._server_thread:
            self._server_thread.join(timeout=5.0)
        self._is_running = False
        self.event_bus.emit("mcp_server_stopped", {})

    def _run_server_thread(self) -> None:
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._run_server())
        except OSError as e:
            if e.errno in (98, 10048):  # Linux / Windows: address already in use
                self._emit_error(f"Порт {self.config.port} занят")
        except Exception as e:
            self._emit_error(str(e))
        finally:
            self._is_running = False
            if self._loop:
                self._loop.close()

    async def _run_server(self) -> None:
        from mcp.server.fastmcp import FastMCP
        from starlette.middleware.cors import CORSMiddleware

        self._mcp = FastMCP("MyApp", json_response=True)
        self._register_tools(self._mcp)
        self._is_running = True

        # Выбор транспорта
        if self.config.sse_enabled:
            base_app = self._mcp.sse_app()
        else:
            base_app = self._mcp.streamable_http_app()

        # TrailingSlash + CORS middlewares (см. ниже)
        app = CORSMiddleware(
            app=TrailingSlashMiddleware(base_app),
            allow_origins=["*"],
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["mcp-protocol-version", "mcp-session-id", "Authorization", "Content-Type"],
            expose_headers=["mcp-session-id"],
        )

        import uvicorn
        config = uvicorn.Config(
            app=app,
            host=self.config.host,
            port=self.config.port,
            log_level="warning",
            access_log=False,
            log_config=None,  # КРИТИЧНО для pythonw.exe: sys.stdout=None там
        )
        self._uvicorn_server = uvicorn.Server(config)
        await self._uvicorn_server.serve()
```

---

## Транспорты: SSE vs Streamable HTTP

MCP поддерживает три транспорта. Выбор транспорта — главная боль совместимости.

### Матрица совместимости (проверено 25 января 2026)

| Клиент | stdio | Streamable HTTP | SSE (legacy) | Примечания |
|--------|-------|-----------------|--------------|------------|
| **Cline** | ✅ | ❌ | ✅ | Только stdio + SSE |
| **Chatbox** | ✅ | ⚠️ | ✅ | Через `npx mcp-remote` как прокси к HTTP |
| **Cursor** | ✅ | ✅ | ✅ | Все три транспорта |
| **VS Code Copilot** | ✅ | ✅ | ✅ | http → fallback на sse |
| **Gemini CLI** | ✅ | ✅ | ✅ | command=stdio, http[url]=HTTP, url=SSE |
| **Qwen Code CLI** | ✅ | ✅ | ✅ | Все три |
| **Claude Code CLI** | ✅ | ✅ | ⚠️ deprecated | HTTP рекомендован |
| **Claude Desktop** | ✅ | ✅ | ✅ | Конфиг через `claude_desktop_config.json` |
| **OpenAI Codex CLI** | ✅ | ✅ | ❌ | stdio + HTTP |

**Вывод:** Держи оба транспорта одновременно (SSE + Streamable HTTP). `sse_enabled=True` — рекомендуемый дефолт для максимальной совместимости.

### Как работает SSE transport

SSE — это Server-Sent Events. Клиент делает `GET /sse`, получает UUID `session_id`. Все последующие запросы — `POST /messages/?session_id=<uuid>`.

**Критичная особенность:** `session_id` хранится в памяти. Рестарт сервера = потеря всех сессий. Клиент получит `500 Error`, пока не переподключится к `/sse` заново.

```
Chatbox → GET /sse
        ← session_id: "c414cf0df71f4..."

Chatbox → POST /messages/?session_id=c414cf0df71f4... {"method": "tools/list"}
        ← 200 OK + tools list

[Server restart]

Chatbox → POST /messages/?session_id=c414cf0df71f4...
        ← 500 Error: session not found
        # Пользователь должен перезапустить Chatbox
```

### Проблема 1: 307 Temporary Redirect (Chatbox баг)

Starlette `Mount()` требует trailing slash. Chatbox шлёт `POST /messages` без слеша → 307 redirect → клиент не следует → зависает.

**Решение: TrailingSlashMiddleware**

```python
class TrailingSlashMiddleware:
    """ASGI middleware: добавляет trailing slash к /messages."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http":
            path = scope.get("path", "")
            method = scope.get("method", "")
            query = scope.get("query_string", b"").decode()
            has_session = "session_id=" in query

            # Логируем БЕЗ конфиденциальных данных
            if path == "/sse" and method == "GET":
                logger.info("mcp.sse.connect client connecting to SSE")
            elif path in ("/messages", "/messages/") and method == "POST":
                logger.info("mcp.http.request has_session=%s", has_session)

            # Фикс trailing slash
            if path == "/messages":
                scope = dict(scope)
                scope["path"] = "/messages/"

        await self.app(scope, receive, send)
```

Применять ДО CORS: `CORSMiddleware(app=TrailingSlashMiddleware(base_app), ...)`.

---

## Написание инструментов

### Главное правило: docstring = промпт для LLM

FastMCP транслирует docstring функции в описание инструмента для агента. Плохой docstring → агент не понимает когда и как использовать tool.

**Шаблон docstring:**

```python
@mcp.tool()
def my_tool(query: str, limit: int = 20) -> list[dict]:
    """Short one-line description.

    USE THIS TOOL WHEN: [trigger conditions]

    TRIGGER PHRASES:
    - "Find me..." -> my_tool(query="...")
    - "Show all..." -> my_tool(limit=50)

    WORKFLOW:
    1. Step one
    2. Step two (use IDs from step one)

    EXAMPLES:
    - my_tool(query="meeting notes")
    - my_tool(query="", limit=5)

    Args:
        query: What to search for. Empty string returns all records.
        limit: Max results (1-100, default 20).

    Returns:
        List of dicts with: id, title, preview, created_at
        OR error dict: {"error": "...", "hint": "..."}
    """
```

**Правила:**

- Docstring на **английском** (агенты международные, MCP клиент может быть любым)
- TRIGGER PHRASES — явно укажи фразы пользователя, на которые реагировать
- WORKFLOW — пошаговый сценарий с связями между инструментами
- Валидация — возвращай `{"error": "...", "hint": "..."}`, никогда не молчи

### Паттерн factory function

Каждый инструмент — `create_<name>_tool(mcp, repository, config, callbacks)`. Closure захватывает зависимости:

```python
def create_search_tool(mcp, repository, config, callbacks):
    """Регистрирует search_transcriptions в MCP."""

    @mcp.tool()
    def search_transcriptions(query: str = "", limit: int = 20) -> list[dict] | dict:
        """..."""
        # Проверяем что tool включён
        if not config.tools.search_transcriptions:
            return {"error": "Tool disabled", "hint": "Enable in Settings > MCP"}

        callbacks["on_started"]("search_transcriptions")
        try:
            results = repository.search_with_filters(query=query, limit=limit)
            callbacks["on_finished"]("search_transcriptions", len(results))
            return [_format_result(r) for r in results]
        except Exception as e:
            callbacks["on_failed"]("search_transcriptions", str(e))
            logger.error("mcp.tool.search.error error=%s", e)
            return {"error": str(e), "hint": "Check database connection"}
```

### Two-Phase Confirm для Write-операций

Любая деструктивная операция требует паттерна подтверждения:

```python
@mcp.tool()
def update_user_notes(id: str, notes: str, confirm: bool = False) -> dict:
    """Update user notes for a transcription.

    ⚠️ WARNING: This MODIFIES user data! Always ask for confirmation first.

    TWO-PHASE CONFIRMATION:
    Phase 1: Call with confirm=False (default) → shows preview, NO changes.
    Phase 2: User confirms → call with confirm=True → applies changes.

    NEVER call with confirm=True without explicit user approval!
    ...
    """
    if not confirm:
        current = repository.get(id)
        return {
            "status": "confirmation_required",
            "current_notes": current.user_notes or "",
            "new_notes": notes,
            "message": "Call again with confirm=True to apply. Current notes shown above."
        }

    repository.update_user_notes(id, notes)
    return {"status": "success", "id": id}
```

### UI-инструменты через EventBus

Единственный правильный способ из asyncio thread управлять Qt UI — EventBus:

```python
def create_open_record_tool(mcp, repository, config, callbacks, event_bus):
    """Регистрирует open_record — открывает окна в приложении."""

    @mcp.tool()
    def open_record(ids: list[str], layer: str = "") -> dict:
        """Open transcription records in the application UI windows.
        ...
        """
        # Emit event — Qt Signal bridge подхватит в main thread
        for record_id in ids:
            event_bus.emit("open_record_requested", {
                "id": record_id,
                "layer": layer,
            })

        return {"status": "success", "opened_count": len(ids)}
```

В Qt main thread подписка:

```python
event_bus.subscribe("open_record_requested", self._on_open_record)

def _on_open_record(self, data: dict) -> None:
    # Здесь уже в main thread, безопасно работать с Qt
    self.record_window_manager.open(data["id"], layer=data.get("layer", ""))
```

---

## Callbacks — мониторинг активных запросов

Callbacks дают серверу знать о ходе выполнения инструментов. Используются для:

- счётчика активных запросов (статус в UI)
- событий EventBus для StatusService
- логирования

```python
callbacks = {
    "on_started": self._on_request_started,
    "on_finished": self._on_request_finished,
    "on_failed": self._on_request_failed,
}

def _on_request_started(self, tool_name: str) -> None:
    self._active_requests += 1
    self.event_bus.emit("mcp_request_started", {
        "tool": tool_name,
        "active_count": self._active_requests,
    })

def _on_request_finished(self, tool_name: str, result_count: int) -> None:
    self._active_requests = max(0, self._active_requests - 1)
    self.event_bus.emit("mcp_request_finished", {
        "tool": tool_name,
        "result_count": result_count,
    })
```

---

## Логирование: приватность прежде всего

MCP-инструменты принимают пользовательский контент (поисковые запросы, тексты заметок). **Никогда не логируй содержимое**.

```python
# ❌ НЕЛЬЗЯ
logger.info("mcp.search query=%s", query)

# ✅ МОЖНО
logger.info("mcp.search query_len=%d limit=%d", len(query), limit)
logger.info("mcp.get ids_count=%d", len(ids))
logger.info("mcp.update id=%s...", id[:8])  # Первые 8 символов UUID для трейса
```

Формат имён логгера: `mcp.tool.<name>.<action>` например `mcp.tool.search.start`, `mcp.tool.search.done`.

---

## Hot-reload конфига

Без перезапуска приложения пользователь может менять порт, включать/выключать SSE, включать/выключать отдельные инструменты. Сервер подписывается на `config_updated`:

```python
self.event_bus.subscribe("config_updated", self._on_config_changed)

def _on_config_changed(self, data: dict) -> None:
    new_mcp = data.get("config").mcp
    old_port = self.config.port
    old_sse = self.config.sse_enabled

    self.config = new_mcp

    if not old_enabled and new_mcp.enabled:
        self.start(); return
    if old_enabled and not new_mcp.enabled:
        self.stop(); return
    if self._is_running and (old_port != new_mcp.port or old_sse != new_mcp.sse_enabled):
        self.stop()
        self.start()
```

Инструменты не перерегистрируются — они проверяют `config.tools.<name>` в runtime при каждом вызове. Изменение флага включает/выключает tool без рестарта.

---

## DI Container: как подключить к приложению

В `main.py` (точка инициализации):

```python
from src.infrastructure.mcp.server import MCPServerManager

def initialize_app(config, event_bus):
    repository = SQLiteRepository(config.database)
    mcp_manager = MCPServerManager(config.mcp, repository, event_bus)

    if config.mcp.enabled:
        mcp_manager.start()

    return AppContainer(
        repository=repository,
        mcp_manager=mcp_manager,
        # ...
    )
```

В `app.py` (entry point, cleanup):

```python
def closeEvent(self, event):
    self.container.mcp_manager.stop()
    super().closeEvent(event)
```

---

## Конфигурация для клиентов

Генерация конфига для Claude Desktop:

```python
def get_claude_desktop_config(self) -> dict:
    return {
        "whisper-voice-machine": {
            "command": "npx",
            "args": ["mcp-remote", self.server_url],
        }
    }
```

`mcp-remote` — прокси от Anthropic, конвертирует stdio ↔ Streamable HTTP. Это рекомендуемый способ подключения Streamable HTTP к клиентам, которые поддерживают только stdio.

Для прямого подключения (Cursor, VS Code):

```json
{
  "servers": {
    "my-app": {
      "type": "http",
      "url": "http://127.0.0.1:7558/mcp"
    }
  }
}
```

Для SSE-only клиентов (Cline, Chatbox):

```json
{
  "mcpServers": {
    "my-app": {
      "type": "sse",
      "url": "http://127.0.0.1:7558/sse"
    }
  }
}
```

---

## Ловушки и решения

### 1. pythonw.exe: `sys.stdout = None`

В режиме GUI-only (без консоли) uvicorn падает при попытке создать `StreamHandler(sys.stdout)`.  
**Решение:** `uvicorn.Config(..., log_config=None)` отключает дефолтный logging uvicorn.

### 2. SSE сессия умирает после рестарта сервера

Сессии хранятся в памяти FastMCP. Рестарт сервера = потеря всех UUID.  
**Решение:** Документировать в UI ("После перезапуска сервера переподключите MCP-клиент").

### 3. Port busy (errno 10048 Windows / 98 Linux)

`OSError` при старте uvicorn если порт занят другим процессом.  
**Решение:** Отлавливать в `_run_server_thread`, отправлять `event_bus.emit("mcp_server_error", ...)` вместо краша.

### 4. Thread-safety для `_active_requests`

Несколько MCP-инструментов могут выполняться параллельно из разных asyncio корутин.  
**Решение:** `threading.Lock` или атомарные операции. В проекте используется `max(0, count - 1)` как защита от гонки.

### 5. Date filtering Edge Case

`datetime.fromisoformat("2026-01-24")` → `2026-01-24 00:00:00`, записи за 24-е число после полуночи не попадают.  
**Решение:**

```python
if date_to:
    parsed = datetime.fromisoformat(date_to)
    if parsed.hour == 0 and parsed.minute == 0:
        parsed = parsed.replace(hour=23, minute=59, second=59)
```

---

## Чеклист при добавлении нового инструмента

```
[ ] Файл tools/my_tool.py с create_my_tool(mcp, repo, config, callbacks)
[ ] @mcp.tool() с docstring: English, TRIGGER PHRASES, WORKFLOW, EXAMPLES, Args/Returns
[ ] Первая строка — проверка config.tools.<name> (включён ли)
[ ] Валидация входных данных → {"error": ..., "hint": ...}
[ ] callbacks["on_started"] / ["on_finished"] / ["on_failed"]
[ ] Write-операции — Two-Phase Confirm (параметр confirm: bool = False)
[ ] Логирование: query_len=, count=, id=first8 — НЕ содержимое
[ ] UI-действия только через event_bus.emit()
[ ] Зарегистрировать в tools/__init__.py → register_all_tools()
[ ] Добавить поле в MCPToolsConfig
[ ] Проверить оба транспорта (SSE + Streamable HTTP)
```

---

## Тестирование вручную

```python
# scripts/test_mcp_manual.py — тест через SSE transport
import requests

# 1. Подключиться к SSE, получить session_id
resp = requests.get("http://127.0.0.1:7558/sse", stream=True)
session_id = parse_session_id(resp)

# 2. initialize
requests.post(f"http://127.0.0.1:7558/messages/?session_id={session_id}",
              json={"jsonrpc": "2.0", "method": "initialize", "id": 1, ...})

# 3. tools/list
requests.post(f"http://127.0.0.1:7558/messages/?session_id={session_id}",
              json={"jsonrpc": "2.0", "method": "tools/list", "id": 2})

# 4. Вызов инструмента
requests.post(f"http://127.0.0.1:7558/messages/?session_id={session_id}",
              json={"jsonrpc": "2.0", "method": "tools/call",
                    "params": {"name": "search_transcriptions", "arguments": {"query": "test"}},
                    "id": 3})
```

Или через MCP Inspector (`npx @modelcontextprotocol/inspector http://127.0.0.1:7558/mcp`) — веб UI для тестирования инструментов.

---

## Связанные эпизоды в архиве

| Эпизод | Что задокументировано |
|--------|----------------------|
| [Episode 30](architecture/season-5-production/30_mcp_server_integration.md) | Первая интеграция. SSE vs Streamable HTTP, TrailingSlashMiddleware, date bug, матрица совместимости |
| [Episode 32](architecture/season-5-production/32_flowlayout_and_record_windows.md) | MCP tool `open_record` — EventBus → UI bridge |
| [Episode 62](architecture/season-6-kill-the-god/62_mcp_server_expansion.md) | Расширение до 7 инструментов. Two-Phase Confirm, privacy logging |
| [Episode 70](architecture/season-6-kill-the-god/70_mcp_search_in_document_tool.md) | `search_in_document` — поиск сегментов/блоков внутри документа |

---

**Конец гайда**
