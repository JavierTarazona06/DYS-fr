"""Resumable, verified download of a local LLM model file.

Deliberately free of any Streamlit import: the UI layer in ``src/ui/model_manager.py``
owns presentation, and keeping this module plain makes it testable without a Streamlit
runtime.

The download runs on a background thread because a 4 GB transfer takes tens of minutes
and Streamlit tears down and re-runs the script on every widget interaction. Progress is
published through :meth:`ModelDownloader.state`, which callers poll.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import threading
from dataclasses import dataclass, replace
from pathlib import Path

import requests

log = logging.getLogger(__name__)

_CHUNK_BYTES = 1024 * 1024
_CONNECT_TIMEOUT = 10
_READ_TIMEOUT = 60
#: Fraction of the expected size required as free disk space before starting.
_DISK_HEADROOM = 1.1


@dataclass(frozen=True)
class DownloadState:
    status: str = "idle"  # idle | running | verifying | done | error | cancelled
    downloaded_bytes: int = 0
    total_bytes: int = 0
    message: str = ""
    destination: Path | None = None

    @property
    def fraction(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return min(1.0, self.downloaded_bytes / self.total_bytes)


class ModelDownloader:
    """Owns at most one in-flight download."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = DownloadState()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None

    # ---------- public API ----------

    def state(self) -> DownloadState:
        with self._lock:
            return self._state

    def is_running(self) -> bool:
        return self.state().status in {"running", "verifying"}

    def cancel(self) -> None:
        """Ask the worker to stop. The partial file is kept so it can resume."""
        self._cancel.set()

    def start(self, entry: dict, models_dir: Path) -> bool:
        """Begin downloading ``entry`` into ``models_dir``. False if already busy."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._cancel.clear()
            self._state = DownloadState(status="running", total_bytes=int(entry.get("size_bytes") or 0))

        self._thread = threading.Thread(
            target=self._run, args=(dict(entry), Path(models_dir)), daemon=True
        )
        self._thread.start()
        return True

    # ---------- internals ----------

    def _set(self, **changes) -> None:
        with self._lock:
            self._state = replace(self._state, **changes)

    def _run(self, entry: dict, models_dir: Path) -> None:
        filename = entry["filename"]
        url = entry["url"]
        expected_sha = (entry.get("sha256") or "").strip().lower()
        expected_size = int(entry.get("size_bytes") or 0)

        final_path = models_dir / filename
        part_path = models_dir / f"{filename}.part"

        try:
            models_dir.mkdir(parents=True, exist_ok=True)

            if final_path.exists():
                self._set(status="done", destination=final_path, message="Le modèle est déjà installé.")
                return

            if expected_size:
                free = shutil.disk_usage(models_dir).free
                if free < expected_size * _DISK_HEADROOM:
                    self._set(
                        status="error",
                        message=(
                            f"Espace disque insuffisant : {free // (1024**3)} Go disponibles, "
                            f"{int(expected_size * _DISK_HEADROOM) // (1024**3)} Go requis."
                        ),
                    )
                    return

            resume_from = part_path.stat().st_size if part_path.exists() else 0
            digest = hashlib.sha256()

            if resume_from:
                # Re-hash what is already on disk so the running digest stays valid.
                log.info("Resuming model download at %s bytes", resume_from)
                with open(part_path, "rb") as handle:
                    while chunk := handle.read(_CHUNK_BYTES):
                        digest.update(chunk)
                        if self._cancel.is_set():
                            self._set(status="cancelled", message="Téléchargement interrompu.")
                            return

            headers = {"Range": f"bytes={resume_from}-"} if resume_from else {}
            response = requests.get(
                url, stream=True, headers=headers, timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT)
            )
            response.raise_for_status()

            if resume_from and response.status_code != 206:
                # The server ignored the range request; start over rather than
                # concatenating a full body onto a partial file.
                log.warning("Server ignored Range request; restarting the download")
                resume_from = 0
                digest = hashlib.sha256()

            total = expected_size or (int(response.headers.get("Content-Length", 0)) + resume_from)
            self._set(total_bytes=total, downloaded_bytes=resume_from)

            mode = "ab" if resume_from else "wb"
            written = resume_from
            with open(part_path, mode) as handle:
                for chunk in response.iter_content(chunk_size=_CHUNK_BYTES):
                    if self._cancel.is_set():
                        self._set(status="cancelled", message="Téléchargement interrompu.")
                        return
                    if not chunk:
                        continue
                    handle.write(chunk)
                    digest.update(chunk)
                    written += len(chunk)
                    self._set(downloaded_bytes=written)

            self._set(status="verifying", message="Vérification de l'intégrité…")

            if expected_size and written != expected_size:
                self._set(
                    status="error",
                    message=f"Taille inattendue : {written} octets reçus, {expected_size} attendus.",
                )
                return

            if expected_sha and digest.hexdigest().lower() != expected_sha:
                # A corrupt or substituted file must never be promoted.
                part_path.unlink(missing_ok=True)
                self._set(
                    status="error",
                    message=(
                        "L'empreinte du fichier téléchargé ne correspond pas. "
                        "Le fichier a été supprimé."
                    ),
                )
                return

            os.replace(part_path, final_path)
            self._set(
                status="done",
                destination=final_path,
                downloaded_bytes=written,
                message="Modèle installé.",
            )
            log.info("Model installed at %s", final_path)

        except Exception as exc:  # noqa: BLE001 - surfaced to the user, logged for support
            log.error("Model download failed", exc_info=True)
            self._set(status="error", message=f"Échec du téléchargement : {exc}")
