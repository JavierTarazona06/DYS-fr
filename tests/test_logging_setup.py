"""Tests for the stdout/stderr shim used in frozen builds.

This object replaces sys.stdout in the packaged application. If it raises, the
exception propagates out of whatever was merely trying to print, and the app dies.
That is not hypothetical: an earlier version accepted only str, and click -- which
writes bytes directly to the stream when it finds no binary writer -- killed the
packaged app while printing Streamlit's startup banner.
"""

from __future__ import annotations

import logging

from src.utils.logging_setup import _StreamToLogger


class _Recorder(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _make_stream() -> tuple[_StreamToLogger, _Recorder]:
    logger = logging.getLogger(f"test.stream.{id(object())}")
    logger.handlers.clear()
    logger.propagate = False
    recorder = _Recorder()
    logger.addHandler(recorder)
    logger.setLevel(logging.INFO)
    return _StreamToLogger(logger, logging.INFO), recorder


def test_forwards_complete_lines():
    stream, recorder = _make_stream()
    stream.write("first line\nsecond line\n")
    assert recorder.messages == ["first line", "second line"]


def test_buffers_partial_lines_until_a_newline_arrives():
    stream, recorder = _make_stream()
    stream.write("half ")
    assert recorder.messages == []
    stream.write("a line\n")
    assert recorder.messages == ["half a line"]


def test_accepts_bytes():
    """click writes bytes straight to the stream; this used to raise TypeError."""
    stream, recorder = _make_stream()
    written = stream.write(b"bytes line\n")
    assert recorder.messages == ["bytes line"]
    assert written == len(b"bytes line\n")


def test_accepts_bytearray_and_memoryview():
    stream, recorder = _make_stream()
    stream.write(bytearray(b"from bytearray\n"))
    stream.write(memoryview(b"from memoryview\n"))
    assert recorder.messages == ["from bytearray", "from memoryview"]


def test_decodes_invalid_utf8_without_raising():
    stream, recorder = _make_stream()
    stream.write(b"caf\xff\n")
    assert len(recorder.messages) == 1


def test_flush_emits_the_trailing_partial_line():
    stream, recorder = _make_stream()
    stream.write("no trailing newline")
    stream.flush()
    assert recorder.messages == ["no trailing newline"]


def test_never_raises_when_the_logger_fails():
    """A broken logging backend must not take the application down."""

    class _Exploding(logging.Handler):
        def emit(self, record):
            raise RuntimeError("handler is broken")

    logger = logging.getLogger("test.stream.exploding")
    logger.handlers.clear()
    logger.propagate = False
    logger.addHandler(_Exploding())
    logger.setLevel(logging.INFO)
    stream = _StreamToLogger(logger, logging.INFO)

    stream.write("this must not raise\n")
    stream.flush()


def test_reports_no_file_descriptor():
    stream, _ = _make_stream()
    try:
        stream.fileno()
    except OSError:
        return
    raise AssertionError("fileno() must raise OSError so callers detect no descriptor")
