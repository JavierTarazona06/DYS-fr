#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

DEFAULT_URL = "http://127.0.0.1:8501"


def wait_http_ready(url: str, *, timeout_s: float) -> bool:
    started = time.time()
    while time.time() - started < timeout_s:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
    else:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the packaged DYS-fr executable.")
    parser.add_argument("--exe", required=True, help="Path to DYS-fr.exe")
    parser.add_argument("--url", default=DEFAULT_URL, help="URL expected to answer with HTTP 200.")
    parser.add_argument("--timeout", type=float, default=60.0, help="Startup timeout in seconds.")
    args = parser.parse_args()

    exe_path = Path(args.exe).resolve()
    if not exe_path.exists():
        raise FileNotFoundError(f"Executable not found: {exe_path}")

    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    process = subprocess.Popen(
        [str(exe_path)],
        cwd=str(exe_path.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )

    try:
        if wait_http_ready(args.url, timeout_s=args.timeout):
            print(f"Smoke test passed: {args.url} responded with HTTP 200.")
            return 0

        if process.poll() is not None:
            raise RuntimeError(f"Packaged executable exited early with code {process.returncode}.")

        raise TimeoutError(f"Timed out waiting for {args.url} to become ready.")
    finally:
        terminate_process_tree(process)


if __name__ == "__main__":
    raise SystemExit(main())
