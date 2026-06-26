"""Root CLI surface for YTDownload 2026."""

from __future__ import annotations

import argparse
import io
import json
import logging
import sys
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from typing import Any, Callable

from src.application.command_api import CommandError

Handler = Callable[[argparse.Namespace], int]
logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_USAGE_ERROR = 2

ROOT_DESCRIPTION = (
    "YTDownload 2026 command-line interface. "
    "Use queue/history/server subcommands; add --help at any level for examples."
)
ROOT_EPILOG = (
    "Examples:\n"
    "  ytdl server http --host 127.0.0.1 --port 8765\n"
    "  ytdl server stdio\n"
    "  ytdl history list --format json\n"
    "  ytdl history file-paths 42 --format pretty\n"
    "  ytdl queue add <url> --quality 720p\n\n"
    "Offline validation:\n"
    "  uv run python scripts/smoke_cli_help.py\n"
    "  uv run python scripts/smoke_mcp.py\n"
    "  uv run python scripts/smoke_mcp_stdio.py"
)

QUEUE_NOTE = (
    "Queue commands are transport-thin wrappers over the shared application API. "
    "By default, destructive actions preview first and require --confirm."
)
HISTORY_NOTE = (
    "History commands are transport-thin wrappers over the shared application API. "
    "Use --format json or global --json for machine-readable output."
)
SERVER_NOTE = "Server commands reuse the shared MCP bootstrap for both HTTP and stdio transports."
QUEUE_EPILOG = (
    "Examples:\n"
    "  ytdl queue add https://youtu.be/dQw4w9WgXcQ --quality 720p\n"
    "  ytdl queue add https://youtu.be/dQw4w9WgXcQ --type audio\n"
    "  ytdl queue cancel 42\n"
    "  ytdl queue cancel 42 --confirm"
)
HISTORY_EPILOG = (
    "Examples:\n"
    "  ytdl history list --format table\n"
    "  ytdl history get 42 --format pretty\n"
    "  ytdl history search python --with-description --format json\n"
    "  ytdl history delete 42 --keep-files\n"
    "  ytdl history delete 42 --confirm"
)
SERVER_EPILOG = (
    "Examples:\n"
    "  ytdl server http --host 127.0.0.1 --port 8765\n"
    "  ytdl server stdio\n\n"
    "Offline validation:\n"
    "  uv run python scripts/smoke_mcp.py\n"
    "  uv run python scripts/smoke_mcp_stdio.py\n\n"
    "Real download/cancel/sidecar validation remains a separate opt-in gate."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ytdl",
        description=ROOT_DESCRIPTION,
        epilog=ROOT_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Force JSON output for command results where applicable.",
    )
    subparsers = parser.add_subparsers(dest="root_command", required=True)

    _add_queue_commands(subparsers)
    _add_history_commands(subparsers)
    _add_server_commands(subparsers)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    services: dict[str, Any] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    setattr(args, "injected_services", services or {})

    from src.core.logging_setup import setup_logging

    log_stream = io.StringIO() if args.json else sys.stderr
    setup_logging(stream=log_stream)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help(sys.stderr)
        return EXIT_USAGE_ERROR

    try:
        return int(handler(args))
    except CommandError as exc:
        if getattr(args, "json", False):
            print(
                json.dumps({"error": exc.message, "hint": exc.hint}, ensure_ascii=False),
                file=sys.stderr,
            )
        else:
            print(f"Error: {exc.message}", file=sys.stderr)
            if exc.hint:
                print(f"Hint: {exc.hint}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    except Exception as exc:
        logger.error("cli.command.failed", exc_info=True)
        if getattr(args, "json", False):
            error_payload: dict[str, Any] = {"error": str(exc)}
            hint = getattr(exc, "hint", None)
            if hint:
                error_payload["hint"] = hint
            print(json.dumps(error_payload, ensure_ascii=False), file=sys.stderr)
        else:
            hint = getattr(exc, "hint", None)
            if hint:
                print(f"Error: {exc}\nHint: {hint}", file=sys.stderr)
            else:
                print(f"Error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR


def _add_queue_commands(subparsers: Any) -> None:
    queue_parser = subparsers.add_parser(
        "queue",
        help="Queue management commands",
        description=QUEUE_NOTE,
        epilog=QUEUE_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    queue_subparsers = queue_parser.add_subparsers(dest="queue_command", required=True)

    add_parser = queue_subparsers.add_parser(
        "add",
        help="Queue a video or playlist download",
        description="Add a video or playlist URL to the download queue.",
    )
    add_parser.add_argument("url")
    add_parser.add_argument("--quality", default="720p")
    add_parser.add_argument(
        "--type",
        dest="download_type",
        default="video",
    )
    add_parser.add_argument("--subtitle-lang")
    add_parser.add_argument("--save-subtitles", action="store_true")
    add_parser.add_argument("--save-description", action="store_true")
    add_parser.add_argument("--save-thumbnail", action="store_true")
    add_parser.add_argument("--format", choices=["json", "text"], default="text")
    add_parser.set_defaults(handler=_handle_queue_add)

    cancel_parser = queue_subparsers.add_parser(
        "cancel",
        help="Cancel a queued or active download",
        description="Preview or cancel a queued/running download. Use --confirm to apply.",
    )
    cancel_parser.add_argument("id", type=int)
    cancel_mode = cancel_parser.add_mutually_exclusive_group()
    cancel_mode.add_argument("--confirm", action="store_true")
    cancel_mode.add_argument("--preview", action="store_true")
    cancel_parser.add_argument("--format", choices=["json", "text"], default="text")
    cancel_parser.set_defaults(handler=_handle_queue_cancel)


def _add_history_commands(subparsers: Any) -> None:
    history_parser = subparsers.add_parser(
        "history",
        help="History and artifact inspection commands",
        description=HISTORY_NOTE,
        epilog=HISTORY_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    history_subparsers = history_parser.add_subparsers(dest="history_command", required=True)

    list_parser = history_subparsers.add_parser(
        "list",
        help="Equivalent to MCP list_downloads(status?, limit?)",
    )
    list_parser.add_argument("--status")
    list_parser.add_argument("--limit", type=int, default=50)
    list_parser.add_argument("--format", choices=["json", "table", "text"], default="table")
    list_parser.set_defaults(handler=_handle_history_list)

    get_parser = history_subparsers.add_parser(
        "get",
        help="Equivalent to MCP get_download(id)",
    )
    get_parser.add_argument("id", type=int)
    get_parser.add_argument("--format", choices=["json", "pretty", "text"], default="pretty")
    get_parser.set_defaults(handler=_handle_history_get)

    search_parser = history_subparsers.add_parser(
        "search",
        help="Equivalent to MCP search_downloads / search_with_description",
    )
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=20)
    search_parser.add_argument("--with-description", action="store_true")
    search_parser.add_argument("--format", choices=["json", "table", "text"], default="table")
    search_parser.set_defaults(handler=_handle_history_search)

    transcript_parser = history_subparsers.add_parser(
        "transcript",
        help="Read subtitles/transcript text",
    )
    transcript_parser.add_argument("id", type=int)
    transcript_parser.add_argument("--lang")
    transcript_parser.add_argument("--raw", action="store_true")
    transcript_parser.add_argument("--timestamps", action="store_true")
    transcript_parser.add_argument(
        "--format",
        choices=["json", "pretty", "text"],
        default="text",
    )
    transcript_parser.set_defaults(handler=_handle_history_transcript)

    description_parser = history_subparsers.add_parser(
        "description",
        help="Equivalent to MCP read_description(id)",
    )
    description_parser.add_argument("id", type=int)
    description_parser.add_argument(
        "--format",
        choices=["json", "pretty", "text"],
        default="text",
    )
    description_parser.set_defaults(handler=_handle_history_description)

    file_paths_parser = history_subparsers.add_parser(
        "file-paths",
        help="Equivalent to MCP get_file_paths(id)",
    )
    file_paths_parser.add_argument("id", type=int)
    file_paths_parser.add_argument(
        "--format",
        choices=["json", "pretty", "text"],
        default="pretty",
    )
    file_paths_parser.set_defaults(handler=_handle_history_file_paths)

    delete_parser = history_subparsers.add_parser(
        "delete",
        help="Delete a history entry and optionally its files",
    )
    delete_parser.add_argument("id", type=int)
    delete_group = delete_parser.add_mutually_exclusive_group()
    delete_group.add_argument(
        "--delete-files",
        dest="delete_files",
        action="store_true",
        default=True,
    )
    delete_group.add_argument("--keep-files", dest="delete_files", action="store_false")
    delete_parser.add_argument("--preview", action="store_true")
    delete_parser.add_argument("--confirm", action="store_true")
    delete_parser.add_argument("--format", choices=["json", "text"], default="text")
    delete_parser.set_defaults(handler=_handle_history_delete)


def _add_server_commands(subparsers: Any) -> None:
    server_parser = subparsers.add_parser(
        "server",
        help="Run the MCP server over HTTP or stdio",
        description=SERVER_NOTE,
        epilog=SERVER_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    server_subparsers = server_parser.add_subparsers(dest="server_command", required=True)

    http_parser = server_subparsers.add_parser(
        "http",
        help="Run the MCP server over HTTP",
        description="Start the MCP server over HTTP at /mcp.",
    )
    http_parser.add_argument("--host", default="127.0.0.1")
    http_parser.add_argument("--port", type=int, default=8765)
    http_parser.set_defaults(handler=_run_server_http)

    stdio_parser = server_subparsers.add_parser(
        "stdio",
        help="Run the MCP server over stdio",
        description="Start the MCP server over stdio for native MCP clients.",
    )
    stdio_parser.set_defaults(handler=_run_server_stdio)


def _handle_queue_add(args: argparse.Namespace) -> int:
    command_api = _get_command_api(args)
    result = command_api.queue_add_download(
        url=args.url,
        quality=args.quality,
        download_type=args.download_type,
        subtitle_lang=args.subtitle_lang,
        save_subtitles=args.save_subtitles,
        save_description=args.save_description,
        save_thumbnail=args.save_thumbnail,
    )
    return _emit_payload(args, result)


def _handle_queue_cancel(args: argparse.Namespace) -> int:
    command_api = _get_command_api(args)
    if args.confirm:
        result = command_api.cancel_download(args.id)
        return _emit_payload(args, result)

    preview = command_api.prepare_cancel_download(args.id)
    payload = _normalize_payload(preview)
    payload["confirmation_required"] = True
    return _emit_payload(args, payload)


def _handle_history_list(args: argparse.Namespace) -> int:
    api = _get_application_api(args)
    result = api.list_downloads(status=args.status, limit=args.limit)
    return _emit_payload(args, result)


def _handle_history_get(args: argparse.Namespace) -> int:
    api = _get_application_api(args)
    result = api.get_download(args.id)
    return _emit_payload(args, result)


def _handle_history_search(args: argparse.Namespace) -> int:
    api = _get_application_api(args)
    result = api.search_downloads(
        args.query,
        limit=args.limit,
        with_description=args.with_description,
    )
    return _emit_payload(args, result)


def _handle_history_transcript(args: argparse.Namespace) -> int:
    api = _get_application_api(args)
    result = api.get_transcript(
        args.id,
        lang=args.lang,
        raw=args.raw,
        timestamps=args.timestamps,
    )
    return _emit_payload(args, result)


def _handle_history_description(args: argparse.Namespace) -> int:
    api = _get_application_api(args)
    result = api.read_description(args.id)
    return _emit_payload(args, result)


def _handle_history_file_paths(args: argparse.Namespace) -> int:
    api = _get_application_api(args)
    result = api.get_file_paths(args.id)
    return _emit_payload(args, result)


def _handle_history_delete(args: argparse.Namespace) -> int:
    command_api = _get_command_api(args)
    if args.confirm and not args.preview:
        result = command_api.delete_download(args.id, delete_files=args.delete_files)
        return _emit_payload(args, result)

    preview = command_api.prepare_delete_download(args.id, delete_files=args.delete_files)
    payload = _normalize_payload(preview)
    payload["confirmation_required"] = True
    return _emit_payload(args, payload)


def _run_server_http(args: argparse.Namespace) -> int:
    from src.interfaces.cli.bootstrap import run_http_server

    services = _ensure_services(args)
    run_http_server(services, host=args.host, port=args.port)
    return EXIT_OK


def _run_server_stdio(args: argparse.Namespace) -> int:
    from src.interfaces.cli.bootstrap import run_stdio_server

    services = _ensure_services(args)
    run_stdio_server(services)
    return EXIT_OK


def _ensure_services(args: argparse.Namespace) -> dict[str, Any]:
    services = getattr(args, "injected_services", None)
    if not services:
        from src.interfaces.cli.bootstrap import initialize_services

        services = initialize_services()
        setattr(args, "injected_services", services)
    return services


def _get_application_api(args: argparse.Namespace) -> Any:
    services = _ensure_services(args)
    api = services.get("application_api")
    if api is None:
        from src.application.api import build_application_api

        api = build_application_api(services)
        services["application_api"] = api
    return api


def _get_command_api(args: argparse.Namespace) -> Any:
    services = _ensure_services(args)
    api = services.get("command_api") or services.get("application_api")
    if api is None:
        from src.application.command_api import build_command_api

        api = build_command_api(services)
        services["command_api"] = api
    return api


def _emit_payload(args: argparse.Namespace, payload: Any) -> int:
    normalized = _normalize_payload(payload)
    if _payload_is_error(normalized):
        if getattr(args, "json", False) or getattr(args, "format", None) == "json":
            print(json.dumps(normalized, ensure_ascii=False), file=sys.stderr)
        else:
            print(_format_error(normalized), file=sys.stderr)
        return EXIT_RUNTIME_ERROR

    if getattr(args, "json", False) or getattr(args, "format", None) == "json":
        print(json.dumps(normalized, ensure_ascii=False))
        return EXIT_OK

    output_format = getattr(args, "format", "text")
    if output_format == "table" and isinstance(normalized, list):
        print(_format_table(normalized))
    elif output_format == "text" and isinstance(normalized, list):
        print(_format_text_rows(normalized))
    elif output_format == "text" and isinstance(normalized, dict):
        if normalized.get("transcript_text") is not None:
            print(normalized["transcript_text"])
        elif normalized.get("description_text") is not None:
            print(normalized["description_text"])
        else:
            print(_format_pretty(normalized))
    elif output_format == "pretty" and isinstance(normalized, dict):
        print(_format_pretty(normalized))
    else:
        print(json.dumps(normalized, ensure_ascii=False, indent=2))
    return EXIT_OK


def _normalize_payload(payload: Any) -> Any:
    if is_dataclass(payload) and not isinstance(payload, type):
        return asdict(payload)
    if isinstance(payload, list):
        return [_normalize_payload(item) for item in payload]
    if isinstance(payload, tuple):
        return [_normalize_payload(item) for item in payload]
    if isinstance(payload, dict):
        return {key: _normalize_payload(value) for key, value in payload.items()}
    return payload


def _payload_is_error(payload: Any) -> bool:
    return isinstance(payload, dict) and isinstance(payload.get("error"), str)


def _format_error(payload: dict[str, Any]) -> str:
    hint = payload.get("hint")
    if hint:
        return f"Error: {payload['error']}\nHint: {hint}"
    return f"Error: {payload['error']}"


def _format_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No results"

    labels = {
        "id": "ID",
        "status": "STATUS",
        "title": "TITLE",
        "download_type": "TYPE",
        "quality": "QUALITY",
        "created_at": "CREATED_AT",
        "description_text": "DESCRIPTION",
    }
    columns = [
        key
        for key in ["id", "status", "title", "download_type", "quality", "created_at"]
        if any(key in row for row in rows)
    ]
    if any("description_text" in row for row in rows):
        columns.append("description_text")
    widths = {
        column: max(
            len(labels.get(column, column)),
            *(len(str(row.get(column, ""))) for row in rows),
        )
        for column in columns
    }
    header = "  ".join(labels.get(column, column).ljust(widths[column]) for column in columns)
    separator = "  ".join("-" * widths[column] for column in columns)
    body = [
        "  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns)
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def _format_text_rows(rows: list[dict[str, Any]]) -> str:
    lines = []
    for row in rows:
        title = row.get("title") or row.get("playlist_title") or ""
        lines.append(f"#{row.get('id')} [{row.get('status')}] {title}".rstrip())
    return "\n".join(lines) if lines else "No results"


def _format_pretty(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in payload.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            if not value:
                lines.append("  -")
            else:
                for item in value:
                    lines.append(f"  - {item}")
            continue
        lines.append(f"{key}: {value}")
    return "\n".join(lines)
