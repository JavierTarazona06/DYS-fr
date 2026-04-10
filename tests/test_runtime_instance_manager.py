from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.runtime import instance_manager as im


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
