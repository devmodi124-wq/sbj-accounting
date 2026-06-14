"""Process/runtime helpers for launching the local app.

Used by the packaged executable (Phase 10) and handy in dev: pick a free port and
open the default browser at the server URL.
"""
from __future__ import annotations

import socket
import threading
import webbrowser


def find_free_port(preferred: int) -> int:
    """Return ``preferred`` if bindable on localhost, else an OS-assigned free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def open_browser_when_ready(url: str, delay: float = 1.0) -> None:
    """Open the default browser at ``url`` shortly after server start."""
    threading.Timer(delay, lambda: webbrowser.open(url)).start()
