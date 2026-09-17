"""The flags the packaged app starts Streamlit with.

Each one is a product decision that nothing else would catch if it were dropped: the app must
stay on the loopback interface, send no usage statistics, and show none of Streamlit's
developer affordances to a dyslexic reader.
"""

from __future__ import annotations

from pathlib import Path

from src.runtime.launcher import _streamlit_argv


def _flags() -> list[str]:
    return _streamlit_argv(Path("app.py"), 8501)


def test_serves_only_on_loopback():
    assert "--server.address=127.0.0.1" in _flags()


def test_sends_no_usage_statistics():
    # The product promises that no data leaves the machine.
    assert "--browser.gatherUsageStats=false" in _flags()


def test_hides_the_deploy_button_but_keeps_user_settings():
    """TODO-17. "viewer", not "minimal": minimal also removes the light/dark theme setting."""
    assert "--client.toolbarMode=viewer" in _flags()


def test_uses_the_port_it_is_given():
    assert "--server.port=8765" in _streamlit_argv(Path("app.py"), 8765)
