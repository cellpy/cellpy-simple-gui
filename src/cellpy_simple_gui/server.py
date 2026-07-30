"""Server helpers shared by the plain-browser and desktop entry points."""

from __future__ import annotations

import socket
import threading
import time

import uvicorn

from .api.app import create_app
from .config import get_settings


def _port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) != 0


def pick_port(host: str, preferred: int) -> int:
    if _port_is_free(host, preferred):
        return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


class ServerThread:
    """Run uvicorn in a background thread so a desktop window can own the main thread."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        config = uvicorn.Config(
            create_app(),
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
            # No FastAPI lifespan hooks — "on" races with force-stop and prints a
            # scary CancelledError traceback on every desktop window close.
            lifespan="off",
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    @property
    def url(self) -> str:
        settings = get_settings()
        return f"http://{self.host}:{self.port}/?token={settings.token}"

    def start(self, wait: bool = True, timeout: float = 20.0) -> None:
        self._thread.start()
        if not wait:
            return
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._server.started:
                return
            time.sleep(0.05)

    def stop(self, join_timeout: float = 2.0) -> None:
        """Ask uvicorn to exit and briefly wait for the daemon thread."""
        self._server.should_exit = True
        # force_exit helps when a request handler is stuck in cellpy I/O
        if hasattr(self._server, "force_exit"):
            self._server.force_exit = True
        if self._thread.is_alive():
            self._thread.join(timeout=join_timeout)
