from __future__ import annotations

import re
from pathlib import Path

from scripts.mcp_expected_tools import EXPECTED_TOOLS, MCP_TOOL_COUNT
from src.infrastructure.mcp.manifest import EXPECTED_MCP_TOOL_SET

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = PROJECT_ROOT / "docs" / "agent-instructions" / "04-mcp-and-gui.md"
README_PATH = PROJECT_ROOT / "README.md"


def test_script_expected_tools_imports_manifest_without_drift() -> None:
    assert EXPECTED_TOOLS == EXPECTED_MCP_TOOL_SET
    assert MCP_TOOL_COUNT == len(EXPECTED_MCP_TOOL_SET)


def test_agent_instruction_tool_list_matches_manifest() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    pattern = (
        r"Expected tools currently include (\d+) user-facing tools:\n\n"
        r"(?P<bullets>(?:- `[^`]+`\n)+)"
    )
    match = re.search(
        pattern,
        content,
    )
    assert match is not None

    doc_count = int(match.group(1))
    doc_tools = {
        item.strip("`")
        for item in re.findall(r"- `([^`]+)`", match.group("bullets"))
    }

    assert doc_count == MCP_TOOL_COUNT
    assert doc_tools == EXPECTED_MCP_TOOL_SET


def test_readme_tool_table_matches_manifest() -> None:
    content = README_PATH.read_text(encoding="utf-8")
    match = re.search(r"управлять загрузками через (\d+) инструментов\.", content)
    assert match is not None

    readme_count = int(match.group(1))
    readme_tools = {
        item.split("(", 1)[0]
        for item in re.findall(r"\| `([^`]+)` \|", content)
        if item.split("(", 1)[0] in EXPECTED_MCP_TOOL_SET
    }

    assert readme_count == MCP_TOOL_COUNT
    assert readme_tools == EXPECTED_MCP_TOOL_SET


def test_readme_and_agent_docs_reference_canonical_stdio_path() -> None:
    doc_content = DOC_PATH.read_text(encoding="utf-8")
    readme_content = README_PATH.read_text(encoding="utf-8")
    expected = "uv run python -m src.interfaces.cli server stdio"

    assert expected in doc_content
    assert expected in readme_content
