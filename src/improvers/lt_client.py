from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any

import requests
from language_tool_python import LanguageTool
from language_tool_python.utils import LanguageToolError, correct


class LTClient:
    """LanguageTool remote client with timeout, retries, and fail-open behavior."""

    def __init__(self, lang: str, server_url: str, *, config: dict[str, Any] | None = None):
        cfg = config or {}
        ping_timeout_s = float(cfg.get("ping_timeout_s", 5))
        self.request_timeout_s = float(cfg.get("request_timeout_s", 30))
        self.check_retries = max(0, int(cfg.get("check_retries", 0)))
        self.retry_backoff_s = max(0.0, float(cfg.get("retry_backoff_s", 0.3)))
        self.fail_open = bool(cfg.get("fail_open", True))
        self.max_chars = max(0, int(cfg.get("max_chars", 0)))
        self.cache_size = max(0, int(cfg.get("cache_size", 128)))

        try:
            response = requests.get(f"{server_url}/v2/languages", timeout=ping_timeout_s)
            if response.status_code != 200:
                raise ConnectionError(f"LanguageTool server returned status {response.status_code}")
        except requests.exceptions.Timeout:
            raise ConnectionError(f"LanguageTool server timeout at {server_url}")
        except requests.exceptions.RequestException as exc:
            raise ConnectionError(f"Cannot connect to LanguageTool server at {server_url}: {exc}")

        self.tool = LanguageTool(lang, remote_server=server_url)
        # language_tool_python defaults to 300s per request; this keeps the UI responsive.
        self.tool._TIMEOUT = self.request_timeout_s

        self._cache: OrderedDict[str, list[Any]] = OrderedDict()
        self._last_warn_ts = 0.0

    def _trim_text(self, text: str) -> str:
        if self.max_chars and len(text) > self.max_chars:
            return text[: self.max_chars]
        return text

    def _warn_once(self, message: str, every_s: float = 15.0) -> None:
        now = time.time()
        if now - self._last_warn_ts >= every_s:
            print(message)
            self._last_warn_ts = now

    def _cache_get(self, text: str):
        if not self.cache_size:
            return None
        cached = self._cache.get(text)
        if cached is None:
            return None
        self._cache.move_to_end(text)
        return cached

    def _cache_put(self, text: str, matches) -> None:
        if not self.cache_size:
            return
        self._cache[text] = matches
        self._cache.move_to_end(text)
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)

    def check(self, text: str):
        if not text:
            return []

        text_to_check = self._trim_text(text)

        cached = self._cache_get(text_to_check)
        if cached is not None:
            return cached

        last_error: Exception | None = None
        attempts = self.check_retries + 1

        for attempt in range(attempts):
            try:
                matches = self.tool.check(text_to_check)
                self._cache_put(text_to_check, matches)
                return matches
            except (LanguageToolError, requests.exceptions.RequestException) as exc:
                last_error = exc
                if attempt < attempts - 1:
                    time.sleep(self.retry_backoff_s * (attempt + 1))
                    continue

        if self.fail_open:
            self._warn_once(
                f"[LT_TIMEOUT] check failed after {attempts} attempt(s). "
                f"Using fail-open mode. Error: {last_error}"
            )
            return []

        raise RuntimeError(f"LanguageTool check failed: {last_error}") from last_error

    def correct_raw(self, text: str) -> str:
        return correct(text, self.check(text))

    def close(self):
        self.tool.close()
