"""Desktop entrypoint for the packaged executable.

Picks a free localhost port, opens the default browser, and serves the app with
Uvicorn. On a locked/first-run database the served UI shows the login/bootstrap
or locked screen (driven by /auth/status), so no special handling is needed here.
"""
from __future__ import annotations

import os
import sys

import uvicorn

from app.config import get_settings
from app.runtime import find_free_port, open_browser_when_ready


def _ensure_std_streams() -> None:
    """A windowed (no-console) PyInstaller exe has sys.stdout/stderr = None, which
    breaks uvicorn's logging setup (the formatter calls sys.stdout.isatty()).
    Point them at a real stream so logging configuration succeeds."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")


def main() -> None:
    _ensure_std_streams()
    settings = get_settings()
    settings.ensure_data_dir()
    port = find_free_port(settings.port)
    url = f"http://127.0.0.1:{port}"
    open_browser_when_ready(url)
    # Import the app object directly (no import-string) so it works when frozen.
    from app.main import app

    # log_config=None avoids uvicorn's default dictConfig (colourized formatters
    # that probe the console), which is fragile in a windowed packaged build.
    uvicorn.run(app, host="127.0.0.1", port=port, log_config=None, log_level="warning")


if __name__ == "__main__":
    main()
