#!/usr/bin/env python
"""
Start LanguageTool server using settings from config.yaml and stop it cleanly on exit.
"""

from __future__ import annotations

import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from src.improvers.lt_server import LanguageToolServer
from src.utils.config import load_config


def _resolve_path_maybe_relative(path_str: str) -> str:
	p = Path(path_str)
	return str(p if p.is_absolute() else (ROOT / p))


def main() -> int:
	cfg = load_config(ROOT / "config.yaml")
	lt_cfg = cfg.get("lt", {})
	srv_cfg = lt_cfg.get("server", {})

	host = srv_cfg.get("host", "127.0.0.1")
	port = int(srv_cfg.get("port", 8081))
	jar_path = _resolve_path_maybe_relative(srv_cfg.get("jar_path", "resources/languagetool/languagetool-server.jar"))
	jre_bin_raw = srv_cfg.get("jre_bin", "java")
	jre_bin = jre_bin_raw if Path(jre_bin_raw).is_absolute() or jre_bin_raw.lower() == "java" else str((ROOT / jre_bin_raw).resolve())
	allow_origin = srv_cfg.get("allow_origin", "*")
	heap_mb = int(srv_cfg.get("heap_mb", 256))

	server = LanguageToolServer(
		host=host,
		port=port,
		jre_bin=jre_bin,
		jar_path=jar_path,
		allow_origin=allow_origin,
		heap_mb=heap_mb,
	)

	def _handle_stop(sig, frame):  # noqa: ARG001
		print("Stopping LanguageTool server...")
		server.stop()
		sys.exit(0)

	with server:
		# Register signal handlers after server is up so we always call stop()
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
