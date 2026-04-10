from __future__ import annotations

import contextlib
import json
import os
import sys
import time
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import psutil

from src.utils.paths import get_project_root, get_user_runtime_dir, is_frozen

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows path
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX path
    msvcrt = None

INSTANCE_METADATA_FILE = "instance.json"
INSTANCE_LOCK_FILE = "instance.lock"
DEFAULT_HTTP_TIMEOUT_S = 1.5
DEFAULT_HEALTH_WAIT_S = 20.0
LOCK_POLL_INTERVAL_S = 0.2


@dataclass(slots=True)
class RunningInstance:
    owner_pid: int
    bundle_root: str
    ui_url: str
    lt_url: str
    started_at: str
    mode: str
    entry_script: str | None = None
    lt_jar_path: str | None = None

    @classmethod
    def from_dict(cls, payload: dict) -> "RunningInstance":
        return cls(
            owner_pid=int(payload["owner_pid"]),
            bundle_root=str(payload["bundle_root"]),
            ui_url=str(payload["ui_url"]),
            lt_url=str(payload["lt_url"]),
            started_at=str(payload["started_at"]),
            mode=str(payload["mode"]),
            entry_script=str(payload["entry_script"]) if payload.get("entry_script") else None,
            lt_jar_path=str(payload["lt_jar_path"]) if payload.get("lt_jar_path") else None,
        )


class InstanceLock(contextlib.AbstractContextManager):
    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self._handle = None
        self.acquired = False

    def acquire(self, *, timeout_s: float = 0.0, poll_interval_s: float = LOCK_POLL_INTERVAL_S) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        if self._handle is None:
            self._handle = open(self.lock_path, "a+b")
            if self._handle.tell() == 0:
                self._handle.write(b"0")
                self._handle.flush()

        deadline = time.monotonic() + max(timeout_s, 0.0)
        while True:
            if self._try_lock():
                self.acquired = True
                self._write_owner_pid()
                return True

            if timeout_s <= 0.0 or time.monotonic() >= deadline:
                return False
            time.sleep(poll_interval_s)

    def release(self) -> None:
        if not self.acquired or self._handle is None:
            return

        try:
            self._unlock()
        finally:
            self.acquired = False
            self._handle.close()
            self._handle = None

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.release()
        return False

    def _try_lock(self) -> bool:
        assert self._handle is not None
        try:
            self._handle.seek(0)
            if os.name == "nt":
                if msvcrt is None:  # pragma: no cover - defensive
                    raise RuntimeError("msvcrt is required on Windows for instance locking.")
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                if fcntl is None:  # pragma: no cover - defensive
                    raise RuntimeError("fcntl is required on POSIX for instance locking.")
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _unlock(self) -> None:
        assert self._handle is not None
        self._handle.seek(0)
        if os.name == "nt":
            if msvcrt is None:  # pragma: no cover - defensive
                raise RuntimeError("msvcrt is required on Windows for instance locking.")
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            if fcntl is None:  # pragma: no cover - defensive
                raise RuntimeError("fcntl is required on POSIX for instance locking.")
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)

    def _write_owner_pid(self) -> None:
        assert self._handle is not None
        payload = f"{os.getpid():>10}".encode("ascii")
        self._handle.seek(0)
        self._handle.write(payload[:1] or b"0")
        self._handle.flush()


def get_instance_lock_path() -> Path:
    return get_user_runtime_dir(create=True) / INSTANCE_LOCK_FILE


def get_instance_metadata_path() -> Path:
    return get_user_runtime_dir(create=True) / INSTANCE_METADATA_FILE


def try_acquire_instance_lock(*, timeout_s: float = 0.0) -> InstanceLock | None:
    lock = InstanceLock(get_instance_lock_path())
    if lock.acquire(timeout_s=timeout_s):
        return lock

    if lock._handle is not None:
        lock._handle.close()
        lock._handle = None
    return None


def build_instance_metadata(*, ui_url: str, lt_url: str, lt_jar_path: str | None = None) -> RunningInstance:
    mode = "frozen" if is_frozen() else "source"
    bundle_root = Path(sys.executable).resolve().parent if is_frozen() else get_project_root().resolve()
    entry_script = None if mode == "frozen" else str((get_project_root() / "runner.py").resolve())

    return RunningInstance(
        owner_pid=os.getpid(),
        bundle_root=str(bundle_root),
        ui_url=ui_url,
        lt_url=lt_url,
        started_at=datetime.now(timezone.utc).isoformat(),
        mode=mode,
        entry_script=entry_script,
        lt_jar_path=lt_jar_path,
    )


def register_instance(instance: RunningInstance) -> None:
    metadata_path = get_instance_metadata_path()
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = metadata_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(asdict(instance), indent=2), encoding="utf-8")
    temp_path.replace(metadata_path)


def load_instance() -> RunningInstance | None:
    metadata_path = get_instance_metadata_path()
    if not metadata_path.exists():
        return None

    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        return RunningInstance.from_dict(payload)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def clear_instance() -> None:
    metadata_path = get_instance_metadata_path()
    with contextlib.suppress(FileNotFoundError):
        metadata_path.unlink()


def open_existing_instance(instance: RunningInstance) -> None:
    webbrowser.open(instance.ui_url)


def is_instance_healthy(instance: RunningInstance, *, timeout_s: float = DEFAULT_HTTP_TIMEOUT_S) -> bool:
    return _url_responds_ok(instance.ui_url, timeout_s=timeout_s) and _url_responds_ok(
        f"{instance.lt_url.rstrip('/')}/v2/languages",
        timeout_s=timeout_s,
    )


def wait_for_existing_instance(*, timeout_s: float = DEFAULT_HEALTH_WAIT_S) -> RunningInstance | None:
    deadline = time.monotonic() + max(timeout_s, 0.0)
    while time.monotonic() < deadline:
        instance = load_instance()
        if instance is None:
            time.sleep(LOCK_POLL_INTERVAL_S)
            continue

        if is_instance_healthy(instance):
            return instance

        if not _pid_exists(instance.owner_pid):
            return None
        time.sleep(LOCK_POLL_INTERVAL_S)
    return None


def cleanup_stale_instance(instance: RunningInstance) -> list[int]:
    targets = _collect_instance_processes(instance)
    if not targets:
        return []

    terminated_pids: list[int] = []
    current_pid = os.getpid()
    candidates = [process for process in targets if process.pid != current_pid]
    if not candidates:
        return []

    for process in _sort_processes_for_shutdown(candidates):
        with contextlib.suppress(psutil.Error):
            process.terminate()

    _, alive = psutil.wait_procs(candidates, timeout=5)
    for process in alive:
        with contextlib.suppress(psutil.Error):
            process.kill()

    psutil.wait_procs(alive, timeout=3)

    for process in candidates:
        with contextlib.suppress(psutil.Error):
            if not process.is_running():
                terminated_pids.append(process.pid)

    return terminated_pids


def _collect_instance_processes(instance: RunningInstance) -> list[psutil.Process]:
    collected: dict[int, psutil.Process] = {}

    owner = _get_process(instance.owner_pid)
    if owner is not None and _matches_owner_process(owner, instance):
        collected[owner.pid] = owner
        for child in owner.children(recursive=True):
            collected[child.pid] = child

    if instance.mode == "frozen":
        bundle_root = _normalize_path(instance.bundle_root)
        for process in psutil.process_iter():
            exe_path = _safe_process_exe(process)
            if exe_path and _path_startswith(exe_path, bundle_root):
                collected[process.pid] = process

    lt_jar_path = _normalize_path(instance.lt_jar_path)
    if lt_jar_path is not None:
        for process in psutil.process_iter():
            if _cmdline_references_path(process, lt_jar_path):
                collected[process.pid] = process

    return list(collected.values())


def _matches_owner_process(process: psutil.Process, instance: RunningInstance) -> bool:
    if process.pid != instance.owner_pid:
        return False

    if instance.mode == "frozen":
        bundle_root = _normalize_path(instance.bundle_root)
        exe_path = _safe_process_exe(process)
        return exe_path is not None and _path_startswith(exe_path, bundle_root)

    entry_script = _normalize_path(instance.entry_script)
    if entry_script is None:
        return False
    return _cmdline_references_path(process, entry_script)


def _cmdline_references_path(process: psutil.Process, expected_path: str) -> bool:
    try:
        cmdline = process.cmdline()
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        return False

    expected_text = os.path.normcase(expected_path)
    for arg in cmdline:
        normalized = _normalize_path(arg)
        if normalized == expected_text:
            return True
        if normalized and expected_text in normalized:
            return True
    return False


def _sort_processes_for_shutdown(processes: Iterable[psutil.Process]) -> list[psutil.Process]:
    def depth(process: psutil.Process) -> int:
        try:
            return len(process.parents())
        except psutil.Error:
            return 0

    return sorted(processes, key=depth, reverse=True)


def _url_responds_ok(url: str, *, timeout_s: float) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as response:
            return response.status == 200
    except Exception:
        return False


def _get_process(pid: int) -> psutil.Process | None:
    try:
        return psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        return psutil.pid_exists(pid)
    except Exception:
        return False


def _safe_process_exe(process: psutil.Process) -> str | None:
    try:
        return _normalize_path(process.exe())
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        return None


def _normalize_path(raw_path: str | os.PathLike[str] | None) -> str | None:
    if raw_path is None:
        return None

    raw_text = str(raw_path).strip().strip('"')
    if not raw_text:
        return None

    try:
        return os.path.normcase(str(Path(raw_text).resolve(strict=False)))
    except OSError:
        return os.path.normcase(raw_text)


def _path_startswith(candidate: str | None, expected_prefix: str | None) -> bool:
    if candidate is None or expected_prefix is None:
        return False

    prefix = expected_prefix.rstrip("\\/")
    if candidate == prefix:
        return True
    return candidate.startswith(prefix + os.sep)
