"""
Pytest fixtures.
Provides lt_server fixture that verifies LT server is running.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

from utils.helpers import ensure_lt_server_running


def pytest_addoption(parser):
	parser.addoption(
		"--lt-url",
		action="store",
		default=None,
		help="Override LanguageTool server URL (e.g., http://127.0.0.1:8081)",
	)


def pytest_configure(config):
	# Make option available to tests via config if needed
	config.addinivalue_line("markers", "lt: tests requiring LanguageTool server")


def _resolve_lt_url(pytestconfig) -> str:
	cli_url = pytestconfig.getoption("--lt-url")
	if cli_url:
		return cli_url
	return ensure_lt_server_running()


def pytest_runtest_setup(item):
	# Tag tests that use lt_server fixture for clarity
	if "lt_server" in item.fixturenames:
		item.add_marker("lt")


import pytest  # noqa: E402, isort:skip


@pytest.fixture(scope="session")
def lt_server(pytestconfig):
	"""Return the LanguageTool server URL, ensuring it's reachable.

	Does **not** start/stop the server; just checks connectivity.
	"""
	url = _resolve_lt_url(pytestconfig)
	print(f"Using LanguageTool server: {url}")
	return url
