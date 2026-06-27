"""Tests for the model downloader.

The module deliberately avoids importing Streamlit so it can be exercised here against
a real local HTTP server, including the paths that only happen on a bad day: a
substituted file, a truncated transfer, and a resumed download.
"""

from __future__ import annotations

import hashlib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from src.services.model_downloader import ModelDownloader

PAYLOAD = bytes(range(256)) * 4096  # 1 MiB, deterministic
PAYLOAD_SHA = hashlib.sha256(PAYLOAD).hexdigest()


class _RangeHandler(BaseHTTPRequestHandler):
    """Serves PAYLOAD, honouring a single-range Range header."""

    supports_range = True

    def do_GET(self):  # noqa: N802 - stdlib naming
        range_header = self.headers.get("Range")
        if range_header and self.supports_range:
            start = int(range_header.split("=", 1)[1].split("-", 1)[0])
            body = PAYLOAD[start:]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}")
        else:
            body = PAYLOAD
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _RangeHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/model.gguf"
    httpd.shutdown()


def _entry(url: str, *, sha: str | None = PAYLOAD_SHA, size: int | None = len(PAYLOAD)) -> dict:
    return {
        "id": "test-model",
        "filename": "model.gguf",
        "url": url,
        "sha256": sha or "",
        "size_bytes": size or 0,
    }


def _run_to_completion(downloader: ModelDownloader, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if downloader.state().status in {"done", "error", "cancelled"}:
            return
        time.sleep(0.05)
    raise AssertionError(f"downloader stuck in state {downloader.state().status}")


def test_downloads_and_promotes_on_matching_hash(server, tmp_path):
    downloader = ModelDownloader()
    assert downloader.start(_entry(server), tmp_path)
    _run_to_completion(downloader)

    state = downloader.state()
    assert state.status == "done", state.message
    assert (tmp_path / "model.gguf").read_bytes() == PAYLOAD
    assert not (tmp_path / "model.gguf.part").exists()


def test_rejects_and_deletes_a_file_with_the_wrong_hash(server, tmp_path):
    """A substituted upstream file must never reach the models directory."""
    downloader = ModelDownloader()
    assert downloader.start(_entry(server, sha="0" * 64), tmp_path)
    _run_to_completion(downloader)

    state = downloader.state()
    assert state.status == "error"
    assert "empreinte" in state.message
    assert not (tmp_path / "model.gguf").exists()
    assert not (tmp_path / "model.gguf.part").exists()


def test_rejects_a_truncated_transfer(server, tmp_path):
    """A size that disagrees with the catalogue is refused before hashing."""
    downloader = ModelDownloader()
    assert downloader.start(_entry(server, sha=None, size=len(PAYLOAD) * 2), tmp_path)
    _run_to_completion(downloader)

    state = downloader.state()
    assert state.status == "error"
    assert "Taille inattendue" in state.message
    assert not (tmp_path / "model.gguf").exists()


def test_resumes_from_an_existing_partial_file(server, tmp_path):
    """A partial file is continued with a Range request, not restarted."""
    partial = tmp_path / "model.gguf.part"
    partial.write_bytes(PAYLOAD[: len(PAYLOAD) // 2])

    downloader = ModelDownloader()
    assert downloader.start(_entry(server), tmp_path)
    _run_to_completion(downloader)

    state = downloader.state()
    assert state.status == "done", state.message
    # The hash only matches if the resumed half was concatenated correctly.
    assert (tmp_path / "model.gguf").read_bytes() == PAYLOAD


def test_restarts_when_the_server_ignores_the_range_request(server, tmp_path, monkeypatch):
    """A server that replies 200 to a Range request must not corrupt the file."""
    monkeypatch.setattr(_RangeHandler, "supports_range", False)
    (tmp_path / "model.gguf.part").write_bytes(PAYLOAD[: len(PAYLOAD) // 2])

    downloader = ModelDownloader()
    assert downloader.start(_entry(server), tmp_path)
    _run_to_completion(downloader)

    state = downloader.state()
    assert state.status == "done", state.message
    assert (tmp_path / "model.gguf").read_bytes() == PAYLOAD


def test_already_installed_is_a_no_op(server, tmp_path):
    (tmp_path / "model.gguf").write_bytes(PAYLOAD)

    downloader = ModelDownloader()
    assert downloader.start(_entry(server), tmp_path)
    _run_to_completion(downloader)

    assert downloader.state().status == "done"


def test_refuses_a_second_concurrent_download(server, tmp_path):
    downloader = ModelDownloader()
    assert downloader.start(_entry(server), tmp_path)
    second = downloader.start(_entry(server), tmp_path)
    _run_to_completion(downloader)

    assert second is False, "a second download must not start while one is in flight"
