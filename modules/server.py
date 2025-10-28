import os, subprocess, atexit
from typing import Optional

from .paths import find_java, find_lt_jar
from .health import wait_until_ready
from .config import ALLOW_ORIGIN

def start_server(port: int, *, java_path: Optional[str] = None, jar_path: Optional[str] = None,
                 allow_origin: str = ALLOW_ORIGIN) -> subprocess.Popen:
    """Start LT server and wait for healthcheck."""
    java = java_path or find_java()
    jar = jar_path or find_lt_jar()

    args = [java, "-jar", jar, "--port", str(port), "--allow-origin", allow_origin]

    creationflags = 0
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW  # hide extra console on Windows

    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    try:
        wait_until_ready(f"http://127.0.0.1:{port}")
    except Exception:
        proc.terminate()
        raise
    return proc

def stop_server(proc: Optional[subprocess.Popen]) -> None:
    if proc and proc.poll() is None:
        proc.terminate()

class LanguageToolServer:
    """Context manager for a local LT HTTP server."""
    def __init__(self, port: int, *, java_path: Optional[str] = None, jar_path: Optional[str] = None,
                 allow_origin: str = ALLOW_ORIGIN):
        self.port = port
        self.java_path = java_path
        self.jar_path = jar_path
        self.allow_origin = allow_origin
        self.proc: Optional[subprocess.Popen] = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> "LanguageToolServer":
        if self.proc is None:
            self.proc = start_server(self.port, java_path=self.java_path,
                                     jar_path=self.jar_path, allow_origin=self.allow_origin)
            atexit.register(self.stop)
        return self

    def stop(self) -> None:
        stop_server(self.proc)
        self.proc = None

    def __enter__(self) -> "LanguageToolServer":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
