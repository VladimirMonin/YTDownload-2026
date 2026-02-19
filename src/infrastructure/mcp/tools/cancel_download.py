"""MCP инструмент: cancel_download — отмена загрузки (двухфазное подтверждение).

Каждый инструмент в отдельном модуле: большие docstring становятся промптами
для LLM-агентов, поэтому читаемость и изоляция критически важны.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def create_cancel_download_tool(mcp: Any, coordinator: Any) -> None:
    """Регистрирует инструмент cancel_download в FastMCP.

    Args:
        mcp: Экземпляр FastMCP.
        coordinator: DownloadCoordinator.
    """

    @mcp.tool()
    def cancel_download(id: int, confirm: bool = False) -> dict:
        """Cancel an active or queued download. Requires two-phase confirmation.

        USE THIS TOOL WHEN:
        - User asks to stop, cancel, or abort a download
        - User wants to remove something from the queue

        TRIGGER PHRASES:
        - "cancel download #5"
        - "stop download 12"
        - "abort the current download"
        - "remove download 3 from the queue"

        ⚠️ TWO-PHASE CONFIRMATION REQUIRED:
        Phase 1: Call with confirm=False (default) → shows preview, NO side effects.
        Phase 2: User confirms → call with confirm=True → cancels the download.

        NEVER call with confirm=True without explicit user approval!

        WORKFLOW:
        1. Call cancel_download(id=X) — returns what will be cancelled.
        2. Show the user the title/status.
        3. Ask "Are you sure you want to cancel this download?"
        4. Only if confirmed: call cancel_download(id=X, confirm=True).

        EXAMPLES:
        - cancel_download(id=5)              → preview (safe, no changes)
        - cancel_download(id=5, confirm=True) → actually cancels

        NOTE: Can only cancel "queued" or "downloading" tasks.
        Already completed/failed/cancelled tasks cannot be cancelled.

        Args:
            id: Numeric download ID to cancel.
            confirm: Must explicitly be True to actually cancel. Default=False (preview).

        Returns:
            If confirm=False: preview dict with title, current status, message.
            If confirm=True: {"id": int, "status": "cancel_requested"}.
            Returns {"error": ..., "hint": ...} if not found or already terminal.
        """
        try:
            task = coordinator.get_task(id)
            if task is None:
                return {
                    "error": f"Download #{id} not found or already finished",
                    "hint": "Use list_downloads() to see active downloads",
                }

            _status = task.status.value if hasattr(task.status, "value") else str(task.status)
            if task.status.is_terminal():
                return {
                    "error": f"Download #{id} is already {_status}",
                    "hint": "Can only cancel 'queued' or 'downloading' tasks",
                }

            if not confirm:
                return {
                    "confirmation_required": True,
                    "id": id,
                    "title": task.title or task.url[:80],
                    "current_status": _status,
                    "message": (
                        f"This will cancel download #{id}: '{task.title or task.url[:60]}'."
                        " Call with confirm=True to proceed."
                    ),
                }

            coordinator.cancel(id)
            logger.info("mcp.cancel_download id=%d", id)
            return {"id": id, "status": "cancel_requested"}

        except Exception as exc:
            logger.error("mcp.cancel_download.error id=%d", id, exc_info=True)
            return {"error": str(exc), "hint": "Check app logs for details"}
