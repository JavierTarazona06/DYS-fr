#!/usr/bin/env python
"""
Quick sanity check for the local LanguageTool download.

- Verifies that resources/languagetool exists
- Checks that languagetool-server.jar is present and reports its size
- Returns exit code 0 on success, 1 otherwise
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LT_DIR = ROOT / "resources" / "languagetool"
LT_JAR = LT_DIR / "languagetool-server.jar"


def main() -> int:
    ok = True

    if not LT_DIR.exists():
        print(f"Missing directory: {LT_DIR}")
        ok = False
    else:
        print(f"Found directory: {LT_DIR}")

    if LT_JAR.exists():
        size_mb = LT_JAR.stat().st_size / (1024 * 1024)
        print(f"Found JAR: {LT_JAR} ({size_mb:.1f} MB)")
    else:
        print(f"Missing JAR: {LT_JAR}")
        ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
