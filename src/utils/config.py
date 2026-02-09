from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.utils.paths import resolve_runtime_path


def _resolve_cfg_path(container: dict[str, Any], key: str) -> None:
    """Resolve a relative path entry in the loaded config to an absolute runtime path."""
    if key not in container:
        return

    value = container[key]
    if value in (None, ""):
        return

    p = Path(str(value))
    if not p.is_absolute():
        container[key] = str(resolve_runtime_path(p))


def load_config(path: str | Path = "config.yaml") -> dict[str, Any]:
    cfg_path = resolve_runtime_path(path)
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f)

    _resolve_cfg_path(cfg["lt"]["server"], "jar_path")

    jre_bin = cfg["lt"]["server"].get("jre_bin", "java")
    if isinstance(jre_bin, str) and jre_bin.lower() != "java":
        p = Path(jre_bin)
        if not p.is_absolute():
            cfg["lt"]["server"]["jre_bin"] = str(resolve_runtime_path(p))

    _resolve_cfg_path(cfg["llm"], "models_dir")
    _resolve_cfg_path(cfg["spacy"], "target_dir")

    cfg["app"] = {
        "config_path": str(cfg_path),
    }
    return cfg
