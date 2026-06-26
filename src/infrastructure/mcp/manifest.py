from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib import import_module
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MCPToolSpec:
    name: str
    registrar_module: str
    registrar_name: str


MCP_TOOL_MANIFEST: tuple[MCPToolSpec, ...] = (
    MCPToolSpec(
        name="list_downloads",
        registrar_module="src.infrastructure.mcp.tools.list_downloads",
        registrar_name="create_list_downloads_tool",
    ),
    MCPToolSpec(
        name="get_download",
        registrar_module="src.infrastructure.mcp.tools.get_download",
        registrar_name="create_get_download_tool",
    ),
    MCPToolSpec(
        name="search_downloads",
        registrar_module="src.infrastructure.mcp.tools.search_downloads",
        registrar_name="create_search_downloads_tool",
    ),
    MCPToolSpec(
        name="search_with_description",
        registrar_module="src.infrastructure.mcp.tools.search_downloads",
        registrar_name="create_search_downloads_tool",
    ),
    MCPToolSpec(
        name="get_file_paths",
        registrar_module="src.infrastructure.mcp.tools.get_file_paths",
        registrar_name="create_get_file_paths_tool",
    ),
    MCPToolSpec(
        name="get_transcript",
        registrar_module="src.infrastructure.mcp.tools.get_transcript",
        registrar_name="create_get_transcript_tool",
    ),
    MCPToolSpec(
        name="read_description",
        registrar_module="src.infrastructure.mcp.tools.read_description",
        registrar_name="create_read_description_tool",
    ),
    MCPToolSpec(
        name="add_download",
        registrar_module="src.infrastructure.mcp.tools.add_download",
        registrar_name="create_add_download_tool",
    ),
    MCPToolSpec(
        name="cancel_download",
        registrar_module="src.infrastructure.mcp.tools.cancel_download",
        registrar_name="create_cancel_download_tool",
    ),
    MCPToolSpec(
        name="delete_download",
        registrar_module="src.infrastructure.mcp.tools.delete_download",
        registrar_name="create_delete_download_tool",
    ),
)

EXPECTED_MCP_TOOL_NAMES: tuple[str, ...] = tuple(spec.name for spec in MCP_TOOL_MANIFEST)
EXPECTED_MCP_TOOL_SET = frozenset(EXPECTED_MCP_TOOL_NAMES)
MCP_TOOL_COUNT = len(EXPECTED_MCP_TOOL_NAMES)


def register_manifest_tools(mcp: Any, application_api: Any) -> None:
    """Register every public MCP tool from the canonical manifest."""
    registered_registrars: set[tuple[str, str]] = set()
    for spec in MCP_TOOL_MANIFEST:
        registrar_key = (spec.registrar_module, spec.registrar_name)
        if registrar_key in registered_registrars:
            continue
        module = import_module(spec.registrar_module)
        registrar = getattr(module, spec.registrar_name)
        registrar(mcp, application_api)
        registered_registrars.add(registrar_key)

    logger.info(
        "mcp.tools.registered count=%d names=%s",
        MCP_TOOL_COUNT,
        ",".join(EXPECTED_MCP_TOOL_NAMES),
    )


__all__ = [
    "EXPECTED_MCP_TOOL_NAMES",
    "EXPECTED_MCP_TOOL_SET",
    "MCP_TOOL_COUNT",
    "MCP_TOOL_MANIFEST",
    "MCPToolSpec",
    "register_manifest_tools",
]