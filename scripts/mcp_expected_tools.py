"""Shared expected MCP tool set for smoke checks."""

from __future__ import annotations

from src.infrastructure.mcp.manifest import EXPECTED_MCP_TOOL_SET, MCP_TOOL_COUNT

EXPECTED_TOOLS = EXPECTED_MCP_TOOL_SET

__all__ = ["EXPECTED_TOOLS", "MCP_TOOL_COUNT"]