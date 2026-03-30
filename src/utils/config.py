from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from src.utils.paths import get_user_config_path, resolve_runtime_path


def _resolve_config_path(path: str | Path | None) -> Path:
    if path is None:
        env_path = os.getenv("DYS_FR_CONFIG")
        if env_path:
            path = env_path
        else:
            path = "config.yaml"

    path = Path(path)
    if path.is_absolute():
        return path
    return resolve_runtime_path(path)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: str | Path | None = None, *, include_user_override: bool = True) -> dict:
    config_path = _resolve_config_path(path)
    with open(config_path, "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    if include_user_override and path is None:
        user_override_path = get_user_config_path(create_parent=False)
        if user_override_path.exists():
            with open(user_override_path, "r", encoding="utf-8") as handle:
                override = yaml.safe_load(handle) or {}
            config = _deep_merge(config, override)

    return config
