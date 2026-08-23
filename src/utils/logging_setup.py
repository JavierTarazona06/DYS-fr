"""Process-wide logging for DYS-fr.

Frozen builds are windowed (``console=False`` in ``packaging/windows/dys_fr.spec``),
so ``sys.stdout`` is ``None`` and every ``print()`` in the codebase is silently
discarded by CPython. Without a log file on disk, a startup failure is an executable
that vanishes with no trace, which is unsupportable on a user's machine.

``configure_logging()`` writes to ``%LOCALAPPDATA%\\DYS-fr\\logs`` and, when frozen,
also redirects ``sys.stdout``/``sys.stderr`` into the same log so existing ``print()``
calls are captured without rewriting every call site.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.utils.paths import get_user_logs_dir, is_frozen

LOG_FILENAME = "dys-fr.log"
LANGUAGETOOL_LOG_FILENAME = "languagetool.log"

_MAX_BYTES = 2 * 1024 * 1024
_BACKUP_COUNT = 3
_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

_configured_path: Path | None = None


class _StreamToLogger:
    """Minimal file-like object forwarding writes to a logger.

    Used only in frozen builds, where the real streams are unusable. Buffers
    partial writes so a single log record is emitted per line.

    Accepts bytes as well as str: click writes bytes straight to the stream when it
    cannot find a binary writer, which is how Streamlit's startup banner reaches us.
    Every method swallows its own errors -- this object exists to record diagnostics,
    so it must never be the thing that takes the application down.
    """

    encoding = "utf-8"
    errors = "replace"

    def __init__(self, logger: logging.Logger, level: int) -> None:
        self._logger = logger
        self._level = level
        self._buffer = ""

    def write(self, message) -> int:
        if not message:
            return 0
        try:
            if isinstance(message, (bytes, bytearray, memoryview)):
                text = bytes(message).decode(self.encoding, self.errors)
            else:
                text = str(message)

            self._buffer += text
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                if line.strip():
                    self._logger.log(self._level, line.rstrip())
        except Exception:
            return len(message)
        return len(message)

    def writelines(self, lines) -> None:
        for line in lines:
            self.write(line)

    def flush(self) -> None:
        try:
            if self._buffer.strip():
                self._logger.log(self._level, self._buffer.rstrip())
            self._buffer = ""
        except Exception:
            self._buffer = ""

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def fileno(self) -> int:
        # click and others probe this; raising OSError is the documented signal that
        # the stream has no underlying descriptor.
        raise OSError("DYS-fr log stream has no file descriptor")


def get_log_path() -> Path | None:
    """Path of the active log file, or None when logging could not be set up."""
    return _configured_path


def get_languagetool_log_path(*, create: bool = False) -> Path | None:
    """Path for the LanguageTool child process log, or None if unavailable."""
    try:
        return get_user_logs_dir(create=create) / LANGUAGETOOL_LOG_FILENAME
    except OSError:
        return None


def configure_logging(level: int = logging.INFO) -> Path | None:
    """Attach a rotating file handler to the root logger. Idempotent.

    Never raises: a machine where the log directory cannot be created must still
    run the application.
    """
    global _configured_path

    if _configured_path is not None:
        return _configured_path

    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter(_FORMAT)

    try:
        log_path = get_user_logs_dir(create=True) / LOG_FILENAME
        handler = RotatingFileHandler(
            log_path,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)
        _configured_path = log_path
    except OSError:
        # No writable log location. Fall through to console logging if we have one.
        _configured_path = None

    if is_frozen():
        if _configured_path is not None:
            sys.stdout = _StreamToLogger(logging.getLogger("stdout"), logging.INFO)
            sys.stderr = _StreamToLogger(logging.getLogger("stderr"), logging.ERROR)
    else:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)

    return _configured_path
