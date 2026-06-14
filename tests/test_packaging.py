"""Phase 10 — packaging entrypoint sanity (the .exe itself is built in CI)."""
from __future__ import annotations

import socket
from pathlib import Path

from app.runtime import find_free_port

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_launcher_has_main():
    from app import launcher

    assert callable(launcher.main)


def test_find_free_port_is_bindable():
    port = find_free_port(8731)
    assert isinstance(port, int) and 0 < port < 65536
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", port))  # should be free right now


def test_spec_file_is_valid_python():
    spec = (REPO_ROOT / "khata.spec").read_text()
    compile(spec, "khata.spec", "exec")  # syntax check (not executed)


def test_workflow_exists():
    assert (REPO_ROOT / ".github" / "workflows" / "build-windows.yml").exists()
