"""Catalogue of locally installable LLM models.

Entries live in ``config.yaml`` under ``llm.downloads`` rather than in code, so a user
config at ``%LOCALAPPDATA%\\DYS-fr\\config.yaml`` can correct a URL or a checksum
without reinstalling the application. That matters: the model is hosted on a third
party whose files can be re-uploaded or re-quantised, and a pinned checksum that goes
stale would otherwise be unfixable on the user's side.
"""

from __future__ import annotations

from pathlib import Path

from src.utils.paths import find_model_file, get_user_models_dir

REQUIRED_FIELDS = ("id", "filename", "url")


def list_entries(cfg: dict) -> list[dict]:
    """Return every well-formed catalogue entry, in config order."""
    raw = (cfg.get("llm") or {}).get("downloads") or []
    entries = []
    for item in raw:
        if isinstance(item, dict) and all(item.get(field) for field in REQUIRED_FIELDS):
            entries.append(dict(item))
    return entries


def get_entry(cfg: dict, entry_id: str) -> dict | None:
    for entry in list_entries(cfg):
        if entry["id"] == entry_id:
            return entry
    return None


def is_installed(cfg: dict, entry: dict) -> bool:
    """True when the model is resolvable by the same search the factory uses.

    Must agree with src/services/factory.py, which resolves models through
    find_model_file: that searches the user models directory *and* the bundled one.
    Checking only the user directory would offer a 4 GB download for a model the
    application can already load.
    """
    configured_dir = (cfg.get("llm") or {}).get("models_dir", "resources/models")
    found, _ = find_model_file(configured_dir, entry["filename"])
    return found is not None


def missing_entries(cfg: dict) -> list[dict]:
    """Catalogue entries the application cannot currently load."""
    return [entry for entry in list_entries(cfg) if not is_installed(cfg, entry)]


def download_destination() -> Path:
    """Where a newly downloaded model is written (searched first by find_model_file)."""
    return get_user_models_dir(create=True)
