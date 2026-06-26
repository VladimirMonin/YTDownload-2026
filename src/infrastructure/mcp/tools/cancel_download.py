"""MCP инструмент: cancel_download — отмена загрузки (двухфазное подтверждение).

Каждый инструмент в отдельном модуле: большие docstring становятся промптами
для LLM-агентов, поэтому читаемость и изоляция критически важны.
"""

from __future__ import annotations

import logging
from typing import Any

from src.application.command_api import CommandError

logger = logging.getLogger(__name__)


def create_cancel_download_tool(mcp: Any, command_api: Any) -> None:
    """Регистрирует инструмент cancel_download в FastMCP.

    Args:
        mcp: Экземпляр FastMCP.
        coordinator: DownloadCoordinator.
    """

    @mcp.tool()
    def cancel_download(id: int, confirm: bool = False) -> dict:
        """Cancel an active or queued download. Requires two-phase confirmation.

        CLI PARITY: `ytdl queue cancel <id> [--confirm]`

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
            if not confirm:
                preview = command_api.prepare_cancel_download(id)
                return {
                    "confirmation_required": True,
                    "id": preview.id,
                    "title": preview.title,
                    "current_status": preview.current_status,
                    "message": (
                        f"This will cancel download #{preview.id}: '{preview.title}'."
                        " Call with confirm=True to proceed."
                    ),
                }

            result = command_api.cancel_download(id)
            logger.info("mcp.cancel_download id=%d", id)
            return {"id": result.id, "status": result.status}
        except CommandError as exc:
            return {"error": exc.message, "hint": exc.hint}
        except Exception as exc:
            logger.error("mcp.cancel_download.error id=%d", id, exc_info=True)
            return {"error": str(exc), "hint": "Check app logs for details"}
