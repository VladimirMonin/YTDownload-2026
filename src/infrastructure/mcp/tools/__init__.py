"""Пакет MCP инструментов YTDownload 2026.

Каждый инструмент — в отдельном модуле. Большие docstring становятся промптами
для LLM-агентов, поэтому читаемость и изоляция критически важны.

Инструменты:
    list_downloads          — список загрузок с фильтром по статусу
    get_download            — детали загрузки по ID (с путями)
    search_downloads        — поиск по названию/URL
    search_with_description — поиск + текст описания ролика из файла
    get_file_paths          — все абсолютные пути к файлам загрузки
    get_transcript          — читает субтитры/транскрипцию из .vtt/.srt файла
    add_download            — добавить URL в очередь (видео, аудио, плейлист)
    cancel_download         — отмена загрузки (двухфазная)
    delete_download         — удаление из истории + файлы с диска (двухфазная)
    read_description        — читает текст .description файла

Готовность к SQLite/PeeWee:
    - history_repo принимает любой IHistoryRepository
    - _utils.py нормализует enum/строки через _ev()
    - Поля в ответах совпадают с будущей схемой таблицы downloads
"""

from __future__ import annotations

from typing import Any

from src.infrastructure.mcp.manifest import register_manifest_tools


def register_all_tools(mcp: Any, services: dict) -> None:
    """Регистрирует все MCP инструменты в FastMCP.

    Вызывается из server.py при создании экземпляра сервера.
    Каждый tool импортируется из своего модуля.

    Args:
        mcp: Экземпляр FastMCP.
        services: Словарь сервисов: application_api и прочие runtime-зависимости.
    """
    application_api = services["application_api"]
    register_manifest_tools(mcp, application_api)


__all__ = ["register_all_tools"]
