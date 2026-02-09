from __future__ import annotations

import sys
from pathlib import Path


def get_project_root() -> Path:
    """Return the repository root when running from source code."""
    return Path(__file__).resolve().parents[2]


def get_executable_dir() -> Path:
    """
    Return the directory that contains the current executable.

    In source mode this maps to the project root.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return get_project_root()


def get_bundle_dir() -> Path:
    """
    Return the directory where bundled files are unpacked by PyInstaller.

    When running from source this maps to the project root.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")).resolve()  # type: ignore[arg-type]
    return get_project_root()


def resolve_runtime_path(path: str | Path) -> Path:
    """
    Resolve a runtime file path for both source and frozen executions.

    Resolution order for relative paths:
    1) executable directory (user-overridable files)
    2) bundle directory (_MEIPASS for PyInstaller)
    """
    p = Path(path)
    if p.is_absolute():
        return p

    candidate = (get_executable_dir() / p).resolve()
    if candidate.exists():
        return candidate

    return (get_bundle_dir() / p).resolve()
