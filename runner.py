from __future__ import annotations

import os
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from src.utils.config import load_config
from src.utils.paths import resolve_runtime_path

# Import shared LT server initialization
sys.path.insert(0, str(Path(__file__).parent))
from scripts.start_lt_server_automatic import start_lt_server_from_config


def _wait_http_ready(url: str, timeout_s: float = 40.0) -> bool:
    """Wait until the given HTTP endpoint responds with status 200."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def _open_browser_when_ready(url: str, timeout_s: float = 40.0) -> None:
    """Open the default browser after Streamlit is reachable."""

    def _worker() -> None:
        if _wait_http_ready(url, timeout_s=timeout_s):
            webbrowser.open(url)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def _run_streamlit(app_script: Path, port: int) -> int:
    """
    Start Streamlit in-process.

    This avoids using `sys.executable -m streamlit`, which breaks in frozen executables.
    """
    from streamlit.web import cli as stcli

    argv_backup = list(sys.argv)
    sys.argv = [
        "streamlit",
        "run",
        str(app_script),
        f"--server.port={port}",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
        "--server.headless=true",
    ]
    try:
        try:
            stcli.main()
            return 0
        except SystemExit as exc:
            code = exc.code
            if isinstance(code, int):
                return code
            return 0 if code in (None, "") else 1
    finally:
        sys.argv = argv_backup


def main() -> int:
    cfg = load_config()
    app_script = resolve_runtime_path("app.py")
    if not app_script.exists():
        raise FileNotFoundError(f"Streamlit app script not found at: {app_script}")

    port = int(os.getenv("STREAMLIT_PORT", "8501"))
    ui_url = f"http://localhost:{port}"

    # Start LT server using shared configuration
    with start_lt_server_from_config() as srv:
        os.environ["LT_URL"] = srv.url
        os.environ["LT_LANG"] = cfg["lt"]["lang"]
        _open_browser_when_ready(ui_url)
        return _run_streamlit(app_script, port)


if __name__ == "__main__":
    raise SystemExit(main())
