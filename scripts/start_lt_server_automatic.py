"""
Helper module to start LanguageTool server from config.yaml.
Used by runner.py to auto-start the server before the UI.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path so we can import src.*
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.improvers.lt_server import LanguageToolServer
from src.utils.config import load_config


def _resolve_path_maybe_relative(path_str: str) -> str:
    p = Path(path_str)
    return str(p if p.is_absolute() else (ROOT / p))


def start_lt_server_from_config() -> LanguageToolServer:
    """
    Reads config.yaml and returns a configured LanguageToolServer instance.
    The instance is a context manager, so use it with 'with'.
    """
    cfg = load_config(ROOT / "config.yaml")
    lt_cfg = cfg.get("lt", {})
    srv_cfg = lt_cfg.get("server", {})

    host = srv_cfg.get("host", "127.0.0.1")
    port = int(srv_cfg.get("port", 8081))
    
    # Resolve JAR path relative to project root
    jar_path_raw = srv_cfg.get("jar_path", "resources/languagetool/languagetool-server.jar")
    jar_path = _resolve_path_maybe_relative(jar_path_raw)
    
    # Resolve JRE path
    jre_bin_raw = srv_cfg.get("jre_bin", "java")
    if Path(jre_bin_raw).is_absolute() or jre_bin_raw.lower() == "java":
        jre_bin = jre_bin_raw
    else:
        jre_bin = str((ROOT / jre_bin_raw).resolve())
        
    allow_origin = srv_cfg.get("allow_origin", "*")
    heap_mb = int(srv_cfg.get("heap_mb", 256))

    return LanguageToolServer(
        host=host,
        port=port,
        jre_bin=jre_bin,
        jar_path=jar_path,
        allow_origin=allow_origin,
        heap_mb=heap_mb,
    )
