from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from src.runtime.instance_manager import (
    build_instance_metadata,
    cleanup_stale_instance,
    clear_instance,
    is_instance_healthy,
    load_instance,
    open_existing_instance,
    register_instance,
    try_acquire_instance_lock,
    wait_for_existing_instance,
)
from src.runtime.languagetool import create_lt_server
from src.utils.config import load_config
from src.utils.paths import resolve_runtime_path

INSTANCE_REUSE_WAIT_S = 20.0
LOCK_RECOVERY_TIMEOUT_S = 10.0


def _is_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) != 0


def _find_available_port(host: str, preferred_port: int) -> int:
    if preferred_port > 0 and _is_port_free(host, preferred_port):
        return preferred_port

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _wait_http_ready(url: str, timeout_s: float = 40.0) -> bool:
    started = time.time()
    while time.time() - started < timeout_s:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def _open_browser_when_ready(url: str, *, enabled: bool, timeout_s: float = 40.0) -> None:
    if not enabled:
        return

    def _worker() -> None:
        if _wait_http_ready(url, timeout_s=timeout_s):
            webbrowser.open(url)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def _run_streamlit(app_script: Path, port: int) -> int:
    from streamlit.web import cli as stcli

    argv_backup = list(sys.argv)
    sys.argv = [
        "streamlit",
        "run",
        str(app_script),
        f"--server.port={port}",
        "--server.address=127.0.0.1",
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
            if isinstance(exc.code, int):
                return exc.code
            return 0 if exc.code in (None, "") else 1
    finally:
        sys.argv = argv_backup


def _reuse_running_instance_if_available() -> bool:
    instance = wait_for_existing_instance(timeout_s=INSTANCE_REUSE_WAIT_S)
    if instance is None:
        return False

    open_existing_instance(instance)
    return True


def _cleanup_registered_instance() -> None:
    instance = load_instance()
    if instance is None:
        return

    cleanup_stale_instance(instance)
    clear_instance()


def main() -> int:
    cfg = load_config()
    app_cfg = cfg.get("app", {})
    lt_server_cfg = cfg.get("lt", {}).get("server", {})

    app_script = resolve_runtime_path("app.py")
    if not app_script.exists():
        raise FileNotFoundError(f"Streamlit app script not found at: {app_script}")

    open_browser = str(app_cfg.get("open_browser", True)).lower() not in {"0", "false", "no", "off"}
    lock = try_acquire_instance_lock()
    if lock is None:
        if _reuse_running_instance_if_available():
            return 0

        _cleanup_registered_instance()
        lock = try_acquire_instance_lock(timeout_s=LOCK_RECOVERY_TIMEOUT_S)
        if lock is None:
            if _reuse_running_instance_if_available():
                return 0
            raise RuntimeError("Could not recover the previous DYS-fr instance.")

    with lock:
        existing_instance = load_instance()
        if existing_instance is not None:
            if is_instance_healthy(existing_instance):
                open_existing_instance(existing_instance)
                return 0
            cleanup_stale_instance(existing_instance)
            clear_instance()

        ui_host = app_cfg.get("host", "127.0.0.1")
        ui_port = _find_available_port(ui_host, int(os.getenv("STREAMLIT_PORT", app_cfg.get("port", 8501))))
        lt_host = lt_server_cfg.get("host", "127.0.0.1")
        lt_port = _find_available_port(lt_host, int(lt_server_cfg.get("port", 8081)))
        ui_url = f"http://{ui_host}:{ui_port}"
        lt_server = create_lt_server(cfg=cfg, port=lt_port)

        register_instance(
            build_instance_metadata(
                ui_url=ui_url,
                lt_url=lt_server.url,
                lt_jar_path=str(lt_server.jar_path),
            )
        )

        try:
            with lt_server as server:
                os.environ["LT_URL"] = server.url
                os.environ["LT_LANG"] = cfg["lt"]["lang"]
                _open_browser_when_ready(ui_url, enabled=open_browser)
                return _run_streamlit(app_script, ui_port)
        finally:
            clear_instance()
