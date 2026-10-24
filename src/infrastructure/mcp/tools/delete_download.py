"""Token-bound history deletion adapter; exact files move to Trash, never a directory tree."""

from __future__ import annotations

import logging
from typing import Any

from src.application.dto import serialize_for_transport
from src.infrastructure.mcp.tools._utils import error_payload

logger = logging.getLogger(__name__)


def create_delete_download_tool(mcp: Any, command_api: Any) -> None:
    @mcp.tool()
    def delete_download(
        id: int,
        delete_files: bool = True,
        confirm: bool = False,
        plan_token: str | None = None,
    ) -> dict[str, Any]:
        """Preview or apply a deletion through the existing application owner.

        CLI PARITY: ytdl history delete ID --preview, then --confirm --plan-token TOKEN.
        First call with confirm=False (default): no effects, exact recorded file list,
        missing/count/root facts and plan_token. Show that plan to the user.
        Only after explicit consent call with the SAME id/delete_files and returned
        plan_token, confirm=True. The digest is not authorization. Missing/changed
        token refuses; repreview and obtain new consent, never automatically retry.

        delete_files=True moves only explicitly attributed regular files to Trash;
        folders/unlisted/shared/unsafe/active targets are never removed. Legacy
        folder-only records safely refuse file deletion. delete_files=False performs
        checked history-only deletion, preserving media, and still requires a token.
        Partial moves/history-save failure return error/code/structured result with
        per-file known outcomes and recovery=repreview, not complete success or Undo.
        """
        try:
            if not confirm:
                preview = command_api.prepare_delete_download(id, delete_files=delete_files)
                payload: dict[str, Any] = serialize_for_transport(preview)
                payload["confirmation_required"] = True
                payload["message"] = _build_preview_message(
                    preview.id,
                    preview.title,
                    preview.output_dir,
                    preview.file_count,
                    preview.delete_files,
                )
                return payload
            result = command_api.delete_download(
                id, delete_files=delete_files, expected_plan=plan_token
            )
            payload = serialize_for_transport(result)
            payload["message"] = f"Download #{result.id} removed from history." + (
                " Known files moved to Trash." if result.files_removed else " No files were moved."
            )
            logger.info("mcp.delete_download id=%d moved_count=%d", id, result.moved_count)
            return payload
        except Exception as error:
            payload = error_payload(error)
            logger.error("mcp.delete_download.failed reason_code=%s", payload["code"])
            return payload


def _build_preview_message(
    id: int,
    title: str,
    output_dir: str | None,
    file_count: int,
    delete_files: bool,
) -> str:
    effect = (
        f"{file_count} explicitly recorded file(s) may move to Trash; directories stay"
        if delete_files
        else "history entry only; files stay"
    )
    return (
        f"Will delete download #{id}: '{title}' ({effect}). "
        "Use confirm=True and the matching plan_token only after user consent."
    )
