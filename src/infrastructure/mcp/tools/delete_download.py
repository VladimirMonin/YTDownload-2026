"""MCP инструмент: delete_download — удаление записи из истории.

Поддерживает удаление файлов с диска через shutil.rmtree.
Двухфазное подтверждение — обязательно.

Каждый инструмент в отдельном модуле: большие docstring становятся промптами
для LLM-агентов, поэтому читаемость и изоляция критически важны.
"""

from __future__ import annotations

import logging
from typing import Any

from src.application.command_api import CommandError

logger = logging.getLogger(__name__)


def create_delete_download_tool(mcp: Any, command_api: Any) -> None:
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

        CLI PARITY: `ytdl history delete <id> [--keep-files|--delete-files] [--confirm]`

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
            if not confirm:
                preview = command_api.prepare_delete_download(id, delete_files=delete_files)
                return {
                    "confirmation_required": True,
                    "id": preview.id,
                    "title": preview.title,
                    "output_dir": preview.output_dir,
                    "file_count": preview.file_count,
                    "delete_files": preview.delete_files,
                    "message": _build_preview_message(
                        preview.id,
                        preview.title,
                        preview.output_dir,
                        preview.file_count,
                        preview.delete_files,
                    ),
                }

            result = command_api.delete_download(id, delete_files=delete_files)
            logger.info("mcp.delete_download id=%d files_removed=%s", id, result.files_removed)

            return {
                "id": result.id,
                "deleted": result.deleted,
                "files_removed": result.files_removed,
                "message": (
                    f"Download #{result.id} removed from history."
                    + (
                        " Files deleted from disk."
                        if result.files_removed
                        else " Files kept on disk."
                    )
                ),
            }
        except CommandError as exc:
            return {"error": exc.message, "hint": exc.hint}
        except Exception as exc:
            logger.error("mcp.delete_download.error id=%d", id, exc_info=True)
            return {"error": str(exc), "hint": "Check app logs for details"}


def _build_preview_message(
    id: int,
    title: str,
    output_dir: str | None,
    file_count: int,
    delete_files: bool,
) -> str:
    parts = [f"Will delete download #{id}: '{title}'."]
    if delete_files:
        if output_dir:
            parts.append(
                f"Will also remove folder '{output_dir}' with {file_count} file(s) from disk."
            )
        else:
            parts.append("No files found on disk to remove.")
    else:
        parts.append("Files will be kept on disk (history entry only).")
    parts.append("Call with confirm=True to proceed.")
    return " ".join(parts)
