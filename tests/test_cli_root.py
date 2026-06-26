from __future__ import annotations

import argparse

import pytest

from src.interfaces.cli import root as cli_root


@pytest.mark.parametrize(
    ("argv", "expected_exit", "expected_text"),
    [
        (["--help"], 0, "queue"),
        (["queue", "--help"], 0, "add"),
        (["history", "--help"], 0, "list"),
        (["server", "--help"], 0, "http"),
    ],
)
def test_help_smoke(argv: list[str], expected_exit: int, expected_text: str, capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        cli_root.main(argv)

    assert exc.value.code == expected_exit
    captured = capsys.readouterr()
    assert expected_text in (captured.out + captured.err)


@pytest.mark.parametrize("argv", [["queue"], ["history"], ["server"]])
def test_missing_leaf_subcommand_uses_usage_exit_code(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli_root.main(argv)

    assert exc.value.code == cli_root.EXIT_USAGE_ERROR


def test_history_list_accepts_json_format() -> None:
    parser = cli_root.build_parser()
    args = parser.parse_args(["history", "list", "--format", "json", "--limit", "7"])

    assert args.root_command == "history"
    assert args.history_command == "list"
    assert args.format == "json"
    assert args.limit == 7


def test_server_http_runtime_failure_returns_nonzero(monkeypatch, capsys) -> None:
    def boom(args: argparse.Namespace) -> int:
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_root, "_run_server_http", boom)

    exit_code = cli_root.main(["server", "http"])

    assert exit_code == cli_root.EXIT_RUNTIME_ERROR
    assert "Error: boom" in capsys.readouterr().err
