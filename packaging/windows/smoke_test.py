#!/usr/bin/env python
"""Smoke-test an installed DYS-fr.

Runs against the application as the Inno Setup installer laid it down, not against
the component downloader. Three things are checked:

1. The UI answers HTTP 200 quickly (the startup reorder must not regress).
2. LanguageTool answers within the overall timeout.
3. The install directory is byte-for-byte unchanged after a full run.

Check 3 is the important one. The app installs into Program Files, which is read-only
for a standard user, so anything writing next to the executable produces an install
that works for the developer and fails for the customer. Ports are discovered from the
instance metadata rather than assumed, so a port fallback does not fail the test.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RUNTIME_IMAGE_NAME = "DYS-fr-runtime.exe"
DEFAULT_EXE = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "DYS-fr" / RUNTIME_IMAGE_NAME

# Files the [Files] section of installer.iss is contracted to place.
REQUIRED_LAYOUT = (
    Path("_internal/resources/languagetool/languagetool-server.jar"),
    Path("_internal/resources/spacy/models/fr_core_news_md/config.cfg"),
    Path("_internal/runtime/jre/bin/java.exe"),
    Path("_internal/config.yaml"),
    Path("_internal/app.py"),
)


def instance_metadata_paths() -> list[Path]:
    """Candidate locations for the running-instance metadata (src/utils/paths.py)."""
    candidates = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "DYS-fr" / "run" / "instance.json")
    candidates.append(Path(os.environ.get("TEMP", "/tmp")) / "dys-fr" / "run" / "instance.json")
    return candidates


def read_instance(started_after: float) -> dict | None:
    """Return instance metadata written by the run under test, if present."""
    for path in instance_metadata_paths():
        try:
            if not path.exists() or path.stat().st_mtime < started_after:
                continue
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return None


def http_ready(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def snapshot_tree(root: Path) -> dict[str, tuple[int, int]]:
    """Map each file under root to (size, mtime_ns)."""
    snapshot: dict[str, tuple[int, int]] = {}
    for path in root.rglob("*"):
        try:
            if path.is_file():
                stat = path.stat()
                snapshot[str(path.relative_to(root))] = (stat.st_size, stat.st_mtime_ns)
        except OSError:
            # A file that vanished mid-walk is itself a change; record it as such.
            snapshot[str(path)] = (-1, -1)
    return snapshot


def diff_snapshots(before: dict, after: dict) -> list[str]:
    problems = []
    for name in sorted(set(after) - set(before)):
        problems.append(f"created: {name}")
    for name in sorted(set(before) - set(after)):
        problems.append(f"deleted: {name}")
    for name in sorted(set(before) & set(after)):
        if before[name] != after[name]:
            problems.append(f"modified: {name}")
    return problems


def kill_stragglers_under(app_dir: Path) -> None:
    """Kill leftovers whose executable lives inside the install directory.

    Scoped on purpose. A blanket `taskkill /IM java.exe` would also kill unrelated
    JVMs on the machine running the test -- an IDE, a build tool, a database.
    The embedded JRE lives under {app}\_internaluntime\jrein, so matching on
    the install path is both sufficient and safe.
    """
    try:
        import psutil
    except ImportError:
        return

    root = str(app_dir).lower()
    for proc in psutil.process_iter(["exe"]):
        try:
            exe = (proc.info.get("exe") or "").lower()
            if exe and exe.startswith(root):
                proc.kill()
        except Exception:
            continue


def terminate(process: subprocess.Popen, app_dir: Path) -> None:
    if process.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True, check=False)
        else:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    kill_stragglers_under(app_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", default=str(DEFAULT_EXE), help="Path to the installed DYS-fr-runtime.exe")
    parser.add_argument("--timeout", type=float, default=90.0, help="Overall readiness timeout in seconds.")
    parser.add_argument("--ui-deadline", type=float, default=20.0, help="Budget for the UI to answer, in seconds.")
    parser.add_argument("--skip-write-check", action="store_true", help="Skip the install-directory immutability check.")
    args = parser.parse_args()

    exe_path = Path(args.exe).resolve()
    if not exe_path.exists():
        print(f"FAIL: executable not found: {exe_path}", file=sys.stderr)
        return 1
    app_dir = exe_path.parent

    failures: list[str] = []

    missing = [str(rel) for rel in REQUIRED_LAYOUT if not (app_dir / rel).exists()]
    if missing:
        failures.append("missing installed files: " + ", ".join(missing))

    before = {} if args.skip_write_check else snapshot_tree(app_dir)

    started_at = time.time()
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    process = subprocess.Popen(
        [str(exe_path)],
        cwd=str(app_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )

    try:
        instance = None
        deadline = started_at + 15.0
        while time.time() < deadline and instance is None:
            instance = read_instance(started_at)
            if instance is None:
                time.sleep(0.25)

        if instance is None:
            failures.append("no instance metadata was written; cannot discover ports")
            ui_url, lt_url = "http://127.0.0.1:8501", "http://127.0.0.1:8081"
        else:
            ui_url = instance.get("ui_url", "")
            lt_url = instance.get("lt_url", "")
            print(f"discovered ui_url={ui_url} lt_url={lt_url}")

        ui_deadline = started_at + args.ui_deadline
        ui_ok = False
        while time.time() < ui_deadline:
            if http_ready(ui_url):
                ui_ok = True
                print(f"UI answered after {time.time() - started_at:.1f}s")
                break
            time.sleep(0.25)
        if not ui_ok:
            failures.append(
                f"UI did not answer within {args.ui_deadline}s "
                "(the UI must start before LanguageTool, see src/runtime/launcher.py)"
            )

        lt_deadline = started_at + args.timeout
        lt_ok = False
        while time.time() < lt_deadline:
            if http_ready(f"{lt_url}/v2/languages"):
                lt_ok = True
                print(f"LanguageTool answered after {time.time() - started_at:.1f}s")
                break
            if process.poll() not in (None, 0):
                break
            time.sleep(0.5)
        if not lt_ok:
            failures.append(f"LanguageTool did not answer within {args.timeout}s")
    finally:
        terminate(process, app_dir)

    if not args.skip_write_check:
        time.sleep(1.0)
        problems = diff_snapshots(before, snapshot_tree(app_dir))
        if problems:
            failures.append(
                "the install directory was modified at runtime, which breaks a "
                "Program Files install for standard users:\n  " + "\n  ".join(problems[:20])
            )

    if failures:
        print("\nSMOKE TEST FAILED", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("\nSmoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
