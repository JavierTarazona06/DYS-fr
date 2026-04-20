"""
Backward-compatible import shim for legacy scripts.
"""
from src.runtime.languagetool import start_lt_server_from_config

__all__ = ["start_lt_server_from_config"]
