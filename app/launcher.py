"""Desktop entrypoint for the packaged executable.

Picks a free localhost port, opens the default browser, and serves the app with
Uvicorn. On a locked/first-run database the served UI shows the login/bootstrap
or locked screen (driven by /auth/status), so no special handling is needed here.
"""
from __future__ import annotations

import uvicorn

from app.config import get_settings
from app.runtime import find_free_port, open_browser_when_ready


def main() -> None:
    settings = get_settings()
    settings.ensure_data_dir()
    port = find_free_port(settings.port)
    url = f"http://127.0.0.1:{port}"
    open_browser_when_ready(url)
    # Import the app object directly (no import-string) so it works when frozen.
    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
