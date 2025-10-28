#!/usr/bin/env python
"""
Download & prepare LanguageTool locally:
- Downloads the snapshot ZIP (unless --no-download is set)
- Extracts to a temp directory
- Renames/moves the top-level LanguageTool folder to ./LanguageTool-6.7
- Deletes the ZIP

Usage:
  python scripts/download_languagetool.py
  python scripts/download_languagetool.py --zip ./LanguageTool-latest-snapshot.zip --no-download
"""

import argparse
import io
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_URL = "https://internal1.languagetool.org/snapshots/LanguageTool-latest-snapshot.zip"
DEFAULT_ZIP = "LanguageTool-latest-snapshot.zip"
DEFAULT_TARGET = "LanguageTool-6.7"

def download(url: str, dest: Path) -> None:
    print(f"Downloading: {url}")
    with urllib.request.urlopen(url) as r:  # no extra deps
        data = r.read()
    dest.write_bytes(data)
    print(f"Saved: {dest} ({dest.stat().st_size // (1024*1024)} MB)")

def find_lt_root(extract_dir: Path) -> Path:
    """Find the extracted LanguageTool folder that contains languagetool-server.jar."""
    for p in extract_dir.iterdir():
        if p.is_dir() and p.name.lower().startswith("languagetool"):
            jar = p / "languagetool-server.jar"
            if jar.exists():
                return p
            # some zips have an extra nesting level
            for sub in p.iterdir():
                if sub.is_dir():
                    jar = sub / "languagetool-server.jar"
                    if jar.exists():
                        return sub
    raise FileNotFoundError("Could not locate the extracted LanguageTool folder with languagetool-server.jar")

def extract(zip_path: Path, target_dir: Path) -> None:
    print(f"Extracting: {zip_path}")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_p = Path(tmpdir)
        # Extract all
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir_p)
        # Locate LT folder
        lt_root = find_lt_root(tmpdir_p)
        # Replace existing target
        if target_dir.exists():
            print(f"Removing existing {target_dir}")
            shutil.rmtree(target_dir)
        print(f"Moving {lt_root} -> {target_dir}")
        shutil.move(str(lt_root), str(target_dir))
    print(f"Ready at: {target_dir}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL, help="Download URL for LanguageTool snapshot ZIP")
    parser.add_argument("--zip", default=DEFAULT_ZIP, help="ZIP file path (download target or existing)")
    parser.add_argument("--target-dir", default=DEFAULT_TARGET, help="Destination folder name")
    parser.add_argument("--no-download", action="store_true", help="Skip download and use existing --zip")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]  # project root (one level above scripts/)
    zip_path = (Path(args.zip) if os.path.isabs(args.zip) else root / args.zip)
    target_dir = (Path(args.target_dir) if os.path.isabs(args.target_dir) else root / args.target_dir)

    if not args.no_download:
        download(args.url, zip_path)
    else:
        if not zip_path.exists():
            print(f"ERROR: --no-download given but ZIP not found: {zip_path}", file=sys.stderr)
            sys.exit(1)

    # Extract & move
    extract(zip_path, target_dir)

    # Cleanup ZIP
    try:
        zip_path.unlink()
        print(f"Deleted ZIP: {zip_path}")
    except Exception as e:
        print(f"Warning: failed to delete ZIP ({e})")

if __name__ == "__main__":
    main()
