"""Canonical MCP composition and explicitly owned HTTP listener (no application owner creation)."""

from __future__ import annotations

import logging
import socket
import sys
import threading
import time
from typing import Any, Callable

from src.application.command_api import CommandError

logger = logging.getLogger(__name__)


def create_mcp_server(services: Any) -> Any:
    """Register the ten existing tools over ONE supplied facade; never initialize a runtime."""
    from fastmcp import FastMCP

    if isinstance(services, dict):
        api, commands = services.get("application_api"), services.get("command_api")
        if api is not None and commands is not None and api is not commands:
            raise CommandError("Service aliases must share one owner", code="INVALID_ARGUMENT")
        api = api if api is not None else commands
    else:
        api = services
    if api is None:
        raise CommandError("An existing Application API is required", code="OWNER_REQUIRED")
    mcp = FastMCP(
        name="ytdownload-2026",
        mask_error_details=True,
        instructions=(
            "YTDownload 2026 MCP server. Tools share one application owner. "
            "Use list_downloads/get_download for state and actual saved paths. "
            "add_download returns acceptance, not completion. Cancel is cooperative intent. "
            "For deletion preview first, obtain user consent, "
            "then pass the same plan_token and mode."
        ),
    )
    from src.infrastructure.mcp.tools import register_all_tools

    register_all_tools(mcp, {"application_api": api})
    logger.info("mcp.server.created count=10")
    return mcp


class HTTPServerHandle:
    """Own only this listener/socket/thread. The supplied application owner is borrowed."""

    def __init__(self, services: Any, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.mcp = create_mcp_server(services)
        self.host, self.port = host, port
        self.server: Any = None
        self.thread: threading.Thread | None = None
        self._socket: socket.socket | None = None
        self._failed = False
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def endpoint(self) -> str:
        return f"http://{self.host}:{self.port}/mcp"

    def start(self, *, timeout: float = 10) -> HTTPServerHandle:
        if self.thread is not None:
            if self.thread.is_alive() and not self._closed:
                return self
            raise CommandError("Listener cannot be restarted", code="RUNTIME_CLOSING")
        if self._closed:
            raise CommandError("Listener is closed", code="RUNTIME_CLOSING")
        stage = "bind"
        try:
            import uvicorn

            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind((self.host, self.port))
            self._socket.listen(128)
            self.port = self._socket.getsockname()[1]
            stage = "startup"
            asgi = self.mcp.http_app(path="/mcp")
            config = uvicorn.Config(
                asgi,
                host=self.host,
                port=self.port,
                log_config=None,
                log_level="critical",
                access_log=False,
                timeout_graceful_shutdown=5,
                proxy_headers=False,
            )
            self.server = uvicorn.Server(config)
            self.thread = threading.Thread(target=self._run, name="mcp-http", daemon=False)
            self.thread.start()
            deadline = time.monotonic() + timeout
            while (
                self.thread.is_alive() and not self.server.started and time.monotonic() < deadline
            ):
                self.thread.join(0.01)
            if not self.server.started or self._failed:
                raise RuntimeError("Listener startup unconfirmed")
            logger.info("mcp.server.started transport=http port=%d", self.port)
            return self
        except BaseException:
            self.close()
            error = CommandError("MCP listener could not start", code="EXECUTION_UNAVAILABLE")
            error.result = {"stage": stage, "port": self.port, "closed": self.closed}
            logger.error("mcp.server.failed reason_code=EXECUTION_UNAVAILABLE")
            raise error from None

    def _run(self) -> None:
        try:
            self.server.run(sockets=[self._socket])
        except BaseException:
            self._failed = True
            logger.error("mcp.server.failed reason_code=INTERNAL_ERROR")

    def join(self, timeout: float | None = None) -> bool:
        if self.thread is not None and self.thread.ident is not None:
            self.thread.join(timeout)
            return not self.thread.is_alive()
        return True

    def close(self, timeout: float | None = None) -> bool:
        if self._closed:
            return True
        if self.server is not None:
            self.server.should_exit = True
        if not self.join(timeout):
            logger.error("mcp.server.close_pending count=1 reason_code=RUNTIME_CLOSING")
            return False
        if self._socket is not None:
            self._socket.close()
        self._closed = True
        logger.info("mcp.server.stopped port=%d", self.port)
        return True


def run_http_server(
    services: Any,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    stop_admission: Callable[[], Any] | None = None,
) -> None:
    handle = HTTPServerHandle(services, host=host, port=port)
    try:
        handle.start()
        print(f"MCP server starting at {handle.endpoint}", file=sys.stderr, flush=True)
        handle.join()
        if handle._failed:
            raise CommandError("MCP listener failed", code="INTERNAL_ERROR")
    finally:
        try:
            if stop_admission is not None:
                stop_admission()
        finally:
            if not handle.close():
                error = CommandError("HTTP transport did not stop", code="EXECUTION_UNAVAILABLE")
                error.result = {"stage": "shutdown", "transport_closed": False}
                raise error


def run_stdio_server(services: Any, *, stop_admission: Callable[[], Any] | None = None) -> None:
    mcp = create_mcp_server(services)
    logger.info("mcp.server.starting transport=stdio")
    try:
        mcp.run(transport="stdio", show_banner=False, log_level="WARNING")
    finally:
        if stop_admission is not None:
            stop_admission()


def run_server(services: Any, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Legacy blocking HTTP wrapper; caller retains the supplied runtime."""
    run_http_server(services, host=host, port=port)


__all__ = [
    "create_mcp_server",
    "run_server",
    "run_http_server",
    "run_stdio_server",
    "HTTPServerHandle",
]

if __name__ == "__main__":
    from src.interfaces.cli import main

    raise SystemExit(main(["server", "http", *sys.argv[1:]]))
