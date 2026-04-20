from __future__ import annotations

import sys
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.runtime import instance_manager as im


class _FakeProcess:
    def __init__(self, pid: int, *, running: bool = True, wait_error: Exception | None = None):
        self.pid = pid
        self._running = running
        self._wait_error = wait_error
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        if self._wait_error is not None:
            raise self._wait_error
        self._running = False
        return 0

    def is_running(self) -> bool:
        return self._running

    def parents(self) -> list[object]:
        return []


def _make_instance() -> im.RunningInstance:
    return im.RunningInstance(
        owner_pid=12345,
        bundle_root=r"Z:\\DYS-fr",
        ui_url="http://127.0.0.1:8501",
        lt_url="http://127.0.0.1:8081",
        started_at="2026-03-31T10:00:00+00:00",
        mode="frozen",
        lt_jar_path=r"Z:\\DYS-fr\\resources\\languagetool\\languagetool-server.jar",
    )


def test_instance_metadata_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(im, "get_user_runtime_dir", lambda create=False: tmp_path)
    instance = _make_instance()

    im.register_instance(instance)
    loaded = im.load_instance()

    assert loaded == instance

    im.clear_instance()
    assert im.load_instance() is None


def test_is_instance_healthy_requires_both_endpoints(monkeypatch):
    instance = _make_instance()

    monkeypatch.setattr(
        im,
        "_url_responds_ok",
        lambda url, timeout_s: url == instance.ui_url or url == f"{instance.lt_url}/v2/languages",
    )
    assert im.is_instance_healthy(instance)

    monkeypatch.setattr(
        im,
        "_url_responds_ok",
        lambda url, timeout_s: url == instance.ui_url,
    )
    assert not im.is_instance_healthy(instance)


def test_cleanup_stale_instance_ignores_access_denied(monkeypatch):
    instance = _make_instance()
    process = _FakeProcess(
        54321,
        wait_error=psutil.AccessDenied(pid=54321),
    )

    monkeypatch.setattr(im, "_collect_instance_processes", lambda _: [process])

    terminated = im.cleanup_stale_instance(instance)

    assert terminated == []
    assert process.terminated
    assert process.killed
