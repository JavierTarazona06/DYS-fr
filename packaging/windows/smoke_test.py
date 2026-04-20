#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
import subprocess
import time
import urllib.request
from pathlib import Path

DEFAULT_URL = "http://127.0.0.1:8501"
RUNTIME_IMAGE_NAME = "DYS-fr-runtime.exe"


def http_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2.0) as response:
            return response.status == 200
    except Exception:
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


def terminate_runtime_processes() -> None:
    if os.name != "nt":
        return
    subprocess.run(
        ["taskkill", "/F", "/T", "/IM", RUNTIME_IMAGE_NAME],
        capture_output=True,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the packaged DYS-fr launcher executable.")
    parser.add_argument("--exe", required=True, help="Path to DYS-fr.exe")
    parser.add_argument("--url", default=DEFAULT_URL, help="URL expected to answer with HTTP 200.")
    parser.add_argument("--runtime-manifest-url", default="", help="Override DYS_FR_RUNTIME_MANIFEST_URL for local tests.")
    parser.add_argument("--timeout", type=float, default=180.0, help="Startup timeout in seconds.")
    args = parser.parse_args()

    exe_path = Path(args.exe).resolve()
    if not exe_path.exists():
        raise FileNotFoundError(f"Executable not found: {exe_path}")

    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    env = os.environ.copy()
    if args.runtime_manifest_url:
        env["DYS_FR_RUNTIME_MANIFEST_URL"] = args.runtime_manifest_url

    process = subprocess.Popen(
        [str(exe_path)],
        cwd=str(exe_path.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        env=env,
    )

    try:
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            if http_ready(args.url):
                print(f"Smoke test passed: {args.url} responded with HTTP 200.")
                return 0

            returncode = process.poll()
            if returncode is not None and returncode != 0:
                raise RuntimeError(f"Packaged executable exited early with code {returncode}.")

            time.sleep(0.5)

        raise TimeoutError(f"Timed out waiting for {args.url} to become ready.")
    finally:
        terminate_process_tree(process)
        terminate_runtime_processes()


if __name__ == "__main__":
    raise SystemExit(main())
