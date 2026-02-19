---
applyTo: "src/infrastructure/mcp/**"
name: "MCPServerInstructions"
description: "MCP Server для YT Downloader — инструменты и архитектура"
---

# 🔌 MCP Server — YT Downloader

**Stack:** FastMCP + uvicorn | **Transport:** Streamable HTTP (`/mcp`) + SSE (`/sse`)

---

## Structure

```
src/infrastructure/mcp/
├── server.py          # Lifecycle: start/stop, transport setup
└── tools/
    ├── __init__.py    # register_all_tools()
    ├── downloads.py   # list_downloads, get_download, search_downloads
    ├── queue.py       # add_to_queue, cancel_download
    └── files.py       # get_file_paths, open_file
```

---

## Tools

| Tool             | File         | Type  | Description                                      |
| ---------------- | ------------ | ----- | ------------------------------------------------ |
| list_downloads   | downloads.py | Read  | Список загрузок с фильтрацией по статусу         |
| get_download     | downloads.py | Read  | Детали загрузки по ID: все пути к файлам         |
| search_downloads | downloads.py | Read  | Поиск по названию/URL                            |
| add_to_queue     | queue.py     | Write | Добавить URL в очередь                           |
| cancel_download  | queue.py     | Write | Отменить загрузку (confirm=True)                 |
| get_file_paths   | files.py     | Read  | Пути: video, audio, subs, description, thumbnail |

---

## Tool Docstrings = LLM Prompts!

- **English** docstrings (MCP клиенты международны)
- Подробно: TRIGGER PHRASES, WORKFLOW, EXAMPLES, Args/Returns
- Валидация: `{"error": ..., "hint": ...}` — не молчать
- Логировать только: `id=`, `count=`, `status=` — **НЕ URLs и не пути**

---

## Destructive Operations (Two-Phase Confirm)

```python
# confirm=False → preview
# confirm=True  → выполняет
async def cancel_download(id: int, confirm: bool = False) -> dict: ...
```

---

## HistoryEntry в MCP ответах

```json
{
  "id": 42,
  "url": "https://youtu.be/...",
  "title": "Video Title",
  "status": "done",
  "quality": "1080p",
  "video_path": "/Downloads/YTDownloader/VideoTitle/video.mp4",
  "audio_path": null,
  "subtitle_paths": ["/Downloads/YTDownloader/VideoTitle/ru.vtt"],
  "description_path": "/Downloads/YTDownloader/VideoTitle/description.txt",
  "thumbnail_path": "/Downloads/YTDownloader/VideoTitle/thumbnail.webp",
  "created_at": "2026-02-19T12:00:00",
  "finished_at": "2026-02-19T12:03:00"
}
```

---

## Adding a New Tool

1. Создай `tools/my_tool.py`
2. Docstring: English, WORKFLOW, EXAMPLES, Args/Returns
3. Зарегистрируй в `tools/__init__.py` → `register_all_tools()`

---

**Конец MCP Instructions**
