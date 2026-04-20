#!/usr/bin/env python
"""
Start LanguageTool server using runtime-aware settings and stop it cleanly on exit.
"""

from __future__ import annotations

import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.languagetool import start_lt_server_from_config
from src.utils.config import load_config


def main() -> int:
    cfg = load_config(ROOT / "config.yaml")
    server = start_lt_server_from_config(cfg=cfg)

    def _handle_stop(sig, frame):  # noqa: ARG001
        print("Stopping LanguageTool server...")
        server.stop()
        sys.exit(0)

    with server:
        signal.signal(signal.SIGINT, _handle_stop)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _handle_stop)
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, _handle_stop)

        print(f"LanguageTool server running at {server.url}.\nPress Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
