from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

APP_NAME = "DYS-fr"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_runtime_root() -> Path:
    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        internal_dir = exe_dir / "_internal"
        if internal_dir.exists():
            return internal_dir
        return exe_dir
    return get_project_root()


def get_bundle_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return get_runtime_root()


def resolve_runtime_path(*parts: str | os.PathLike[str]) -> Path:
    path = get_runtime_root()
    for part in parts:
        path = path / Path(part)
    return path


def resolve_bundle_path(*parts: str | os.PathLike[str]) -> Path:
    path = get_bundle_root()
    for part in parts:
        path = path / Path(part)
    return path


def _default_user_base() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data)

    if os.name == "nt":
        return Path.home() / "AppData" / "Local"

    return Path.home() / ".local" / "share"


def get_user_data_dir(*, create: bool = False) -> Path:
    path = _default_user_base() / APP_NAME
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def get_user_config_path(*, create_parent: bool = False) -> Path:
    return get_user_data_dir(create=create_parent) / "config.yaml"


def get_user_models_dir(*, create: bool = False) -> Path:
    path = get_user_data_dir(create=create) / "models"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def get_user_logs_dir(*, create: bool = False) -> Path:
    path = get_user_data_dir(create=create) / "logs"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_existing_path(path_str: str | os.PathLike[str]) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return resolve_runtime_path(path)


def iter_model_search_paths(configured_models_dir: str | os.PathLike[str]) -> Iterable[Path]:
    user_models_dir = get_user_models_dir(create=False)
    runtime_models_dir = resolve_existing_path(configured_models_dir)
    yield user_models_dir
    yield runtime_models_dir


def find_model_file(
    configured_models_dir: str | os.PathLike[str],
    filename: str,
) -> tuple[Path | None, list[Path]]:
    candidates = [candidate / filename for candidate in iter_model_search_paths(configured_models_dir)]
    for candidate in candidates:
        if candidate.exists():
            return candidate, candidates
    return None, candidates
