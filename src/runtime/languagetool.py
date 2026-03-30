from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

from src.improvers.lt_server import LanguageToolServer
from src.utils.config import load_config
from src.utils.paths import resolve_runtime_path


def _resolve_runtime_relative(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return resolve_runtime_path(path)


def _resolve_jre_bin(jre_bin_raw: str) -> str:
    normalized = (jre_bin_raw or "auto").strip()

    if normalized.lower() == "auto":
        embedded_java = resolve_runtime_path("runtime", "jre", "bin", "java.exe")
        if embedded_java.exists():
            return str(embedded_java)
        return "java"

    if normalized.lower() == "java":
        return "java"

    path = Path(normalized)
    if path.is_absolute():
        return str(path)

    return str(resolve_runtime_path(path))


def create_lt_server(cfg: dict | None = None, *, port: int | None = None) -> LanguageToolServer:
    cfg = deepcopy(cfg) if cfg is not None else load_config()
    lt_cfg = cfg.get("lt", {})
    server_cfg = lt_cfg.get("server", {})

    host = server_cfg.get("host", "127.0.0.1")
    resolved_port = int(port if port is not None else server_cfg.get("port", 8081))
    allow_origin = server_cfg.get("allow_origin", "*")
    heap_mb = int(server_cfg.get("heap_mb", 256))

    jar_path = _resolve_runtime_relative(
        server_cfg.get("jar_path", "resources/languagetool/languagetool-server.jar")
    )
    jre_bin = _resolve_jre_bin(server_cfg.get("jre_bin", "auto"))

    return LanguageToolServer(
        host=host,
        port=resolved_port,
        jre_bin=jre_bin,
        jar_path=str(jar_path),
        allow_origin=allow_origin,
        heap_mb=heap_mb,
    )


def start_lt_server_from_config(cfg: dict | None = None, *, port: int | None = None) -> LanguageToolServer:
    return create_lt_server(cfg=cfg, port=port)

