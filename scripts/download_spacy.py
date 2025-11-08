#!/usr/bin/env python
"""
Download and install a spaCy model wheel for offline installation.

This script runs:
    python -m spacy info <model> --url
    python -m pip install --no-deps <wheel>
    python -m spacy validate
to obtain the deterministic download URL, download the wheel into the project's
resources directory (default: resources/spacy), install it, and validate the setup.

Usage:
    python scripts/download_spacy.py
    python scripts/download_spacy.py --model fr_core_news_md
    python scripts/download_spacy.py --target-dir ./resources/spacy --force-reinstall
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import load_config


cfg = load_config()
spacy = cfg["spacy"]

DEFAULT_MODEL = spacy["model"]
DEFAULT_TARGET_DIR = spacy["target_dir"]


def resolve_path(path: str | Path, root: Path) -> Path:
    """Resolve a potentially relative path against project root."""
    path = Path(path)
    return path if path.is_absolute() else (root / path)


def get_model_url(python_exec: str, model: str) -> str:
    """Invoke `python -m spacy info <model> --url` and return the download URL."""
    cmd = [python_exec, "-m", "spacy", "info", model, "--url"]
    print(f"Running: {' '.join(cmd)}")
    completed = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
    )
    stdout = completed.stdout.strip()
    if not stdout:
        raise RuntimeError("spaCy info returned no output.")

    # The URL is typically the last line of stdout.
    url = stdout.splitlines()[-1].strip()
    if not url.lower().startswith(("http://", "https://")):
        raise RuntimeError(f"Unexpected output when parsing URL:\n{stdout}")
    return url


def download(url: str, destination: Path, force_reinstall: bool) -> Path:
    """Download the URL into destination. Returns the path to the saved file."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and not force_reinstall:
        size_mb = destination.stat().st_size / (1024 * 1024)
        print(
            f"Wheel already exists, reusing: {destination} ({size_mb:.2f} MB)"
        )
        return destination

    if destination.exists() and force_reinstall:
        print(f"Overwriting existing wheel (--force-reinstall): {destination}")

    print(f"Downloading: {url}")
    with urllib.request.urlopen(url) as response:
        data = response.read()
    destination.write_bytes(data)

    size_mb = destination.stat().st_size / (1024 * 1024)
    print(f"Saved: {destination} ({size_mb:.2f} MB)")
    return destination


def install_wheel(python_exec: str, wheel_path: Path, force_reinstall: bool) -> None:
    """Install the downloaded wheel using pip."""
    if not wheel_path.exists():
        raise FileNotFoundError(f"Wheel not found: {wheel_path}")

    cmd = [python_exec, "-m", "pip", "install", "--no-deps"]
    if force_reinstall:
        cmd.append("--force-reinstall")
    cmd.append(str(wheel_path))

    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def run_spacy_validate(python_exec: str) -> None:
    """Run `python -m spacy validate` with the given interpreter."""
    cmd = [python_exec, "-m", "spacy", "validate"]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, text=True, capture_output=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download a spaCy model wheel using `python -m spacy info --url`."
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="spaCy model name to download (default: %(default)s)",
    )
    parser.add_argument(
        "--target-dir",
        default=DEFAULT_TARGET_DIR,
        help="Directory where the wheel will be stored (default: %(default)s)",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use for running spaCy (default: current interpreter)",
    )
    parser.add_argument(
        "--force-reinstall",
        action="store_true",
        dest="force_reinstall",
        help=(
            "Re-download the wheel if it exists and force pip to reinstall the model."
        ),
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    python_exec = args.python
    if not os.path.isabs(python_exec):
        python_exec = sys.executable if args.python == sys.executable else str(
            resolve_path(args.python, project_root)
        )
    python_exec = str(python_exec)

    target_dir = resolve_path(args.target_dir, project_root)

    try:
        url = get_model_url(python_exec, args.model)
    except subprocess.CalledProcessError as exc:
        print("Failed to query spaCy for the download URL.", file=sys.stderr)
        print(exc.stderr, file=sys.stderr)
        sys.exit(exc.returncode)
    except Exception as exc:
        print(f"Error determining model URL: {exc}", file=sys.stderr)
        sys.exit(1)

    filename = Path(urllib.parse.urlparse(url).path).name
    if not filename:
        print(f"Could not deduce filename from URL: {url}", file=sys.stderr)
        sys.exit(1)

    destination = target_dir / filename

    try:
        wheel_path = download(url, destination, args.force_reinstall)
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        install_wheel(python_exec, wheel_path, args.force_reinstall)
    except subprocess.CalledProcessError as exc:
        print("pip install failed.", file=sys.stderr)
        sys.exit(exc.returncode)
    except Exception as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        run_spacy_validate(python_exec)
    except subprocess.CalledProcessError as exc:
        print("spaCy validate reported issues:", file=sys.stderr)
        print(exc.stdout, file=sys.stderr)
        print(exc.stderr, file=sys.stderr)
        sys.exit(exc.returncode)

    print("Done.")


if __name__ == "__main__":
    main()

