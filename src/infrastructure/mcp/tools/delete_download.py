"""MCP инструмент: delete_download — удаление записи из истории.

Поддерживает удаление файлов с диска через shutil.rmtree.
Двухфазное подтверждение — обязательно.

Каждый инструмент в отдельном модуле: большие docstring становятся промптами
для LLM-агентов, поэтому читаемость и изоляция критически важны.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from ._utils import entry_to_dict_short

logger = logging.getLogger(__name__)


def create_delete_download_tool(mcp: Any, history_repo: Any) -> None:
    """Регистрирует инструмент delete_download в FastMCP.

    Args:
        mcp: Экземпляр FastMCP.
        history_repo: IHistoryRepository.
    """

    @mcp.tool()
    def delete_download(
        id: int,
        delete_files: bool = True,
        confirm: bool = False,
    ) -> dict:
        """Delete a download entry from history, optionally removing files from disk.

        USE THIS TOOL WHEN:
        - User asks to delete, remove, or clean up a download
        - User wants to free disk space from downloaded files
        - User wants to remove entries from history

        TRIGGER PHRASES:
        - "delete download #5"
        - "remove download 10 from history"
        - "clean up download 3 and its files"
        - "delete download 7 but keep the files"
        - "remove all trace of download 12"

        ⚠️ TWO-PHASE CONFIRMATION REQUIRED — THIS IS DESTRUCTIVE:
        Phase 1: Call with confirm=False (default) → shows preview, NOTHING deleted.
        Phase 2: User confirms → call with confirm=True → deletes entry (and files if requested).

        NEVER call with confirm=True without explicit user approval!

        WORKFLOW:
        1. Call delete_download(id=X) or delete_download(id=X, delete_files=False).
           → Returns preview: title, folder path that will be deleted, file list.
        2. Show the preview to the user clearly.
        3. Ask: "Delete download #{id} [and all its files]? (yes/no)"
        4. Only if user confirms: call delete_download(id=X, delete_files=..., confirm=True).

        delete_files=True  → removes the entire output folder from disk (shutil.rmtree).
                             Use when user wants to free disk space.
        delete_files=False → only removes the history record, files stay on disk.
                             Use when user wants to keep the files but clean the list.

        EXAMPLES:
        - delete_download(id=5)
            → preview (safe, shows what will be deleted)
        - delete_download(id=5, delete_files=True, confirm=True)
            → deletes history entry AND removes files from disk
        - delete_download(id=5, delete_files=False, confirm=True)
            → deletes only the history entry, files stay on disk

        Args:
            id: Numeric download ID to delete.
            delete_files: If True, also removes files from disk (default True).
            confirm: Must be True to actually delete. Default=False (preview only).

        Returns:
            If confirm=False: preview dict with title, output_dir, file_count, message.
            If confirm=True: {"id": int, "deleted": True, "files_removed": bool}.
            Returns {"error": ..., "hint": ...} if not found.
        """
        try:
            entry = history_repo.get_by_id(id)
            if entry is None:
                return {
                    "error": f"Download #{id} not found",
                    "hint": "Use list_downloads() to see valid IDs",
                }

            # Определяем папку для удаления
            folder = _resolve_folder(entry)
            file_count = _count_files(folder) if folder else 0

            if not confirm:
                # Фаза 1: показываем превью, ничего не делаем
                return {
                    "confirmation_required": True,
                    "id": id,
                    "title": entry.playlist_title or entry.title or entry.url[:80],
                    "output_dir": str(folder) if folder else None,
                    "file_count": file_count,
                    "delete_files": delete_files,
                    "message": _build_preview_message(id, entry, folder, file_count, delete_files),
                }

            # Фаза 2: фактическое удаление
            files_removed = False
            if delete_files and folder and folder.exists():
                try:
                    shutil.rmtree(folder)
                    files_removed = True
                    logger.info(
                        "mcp.delete_download.files_removed id=%d path_len=%d",
                        id,
                        len(str(folder)),
                    )
                except Exception:
                    logger.error("mcp.delete_download.rmtree_failed id=%d", id, exc_info=True)

            history_repo.delete(id)
            logger.info("mcp.delete_download id=%d files_removed=%s", id, files_removed)

            return {
                "id": id,
                "deleted": True,
                "files_removed": files_removed,
                "message": (
                    f"Download #{id} removed from history."
                    + (" Files deleted from disk." if files_removed else " Files kept on disk.")
                ),
            }

        except Exception as exc:
            logger.error("mcp.delete_download.error id=%d", id, exc_info=True)
            return {"error": str(exc), "hint": "Check app logs for details"}


def _resolve_folder(entry: Any) -> Path | None:
    """Определяет папку для удаления с диска.

    Приоритет: output_dir (папка плейлиста/видео) → папка video_path → папка audio_path.
    Готово к SQLite: поля те же, просто другой источник данных.
    """
    if entry.output_dir:
        p = Path(entry.output_dir)
        if p.exists():
            return p
    if entry.video_path:
        p = Path(entry.video_path).parent
        if p.exists():
            return p
    if entry.audio_path:
        p = Path(entry.audio_path).parent
        if p.exists():
            return p
    return None


def _count_files(folder: Path) -> int:
    """Считает количество файлов в папке рекурсивно."""
    try:
        return sum(1 for _ in folder.rglob("*") if _.is_file())
    except Exception:
        return 0


def _build_preview_message(
    id: int,
    entry: Any,
    folder: Path | None,
    file_count: int,
    delete_files: bool,
) -> str:
    title = entry.playlist_title or entry.title or entry.url[:60]
    parts = [f"Will delete download #{id}: '{title}'."]
    if delete_files:
        if folder:
            parts.append(f"Will also remove folder '{folder}' with {file_count} file(s) from disk.")
        else:
            parts.append("No files found on disk to remove.")
    else:
        parts.append("Files will be kept on disk (history entry only).")
    parts.append("Call with confirm=True to proceed.")
    return " ".join(parts)
