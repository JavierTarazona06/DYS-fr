from typing import Callable, Iterable
from language_tool_python import Match
from language_tool_python.utils import correct as lt_correct

def default_filter(m: Match) -> bool:
    """Return True to keep the match. Here: ignore ALL-CAPS tokens for 'Possible spelling mistake'."""
    if m.message != 'Possible spelling mistake found.' or not m.replacements:
        return True
    original = m.context[m.offsetInContext:m.offsetInContext + m.errorLength]
    return not original.isupper()

def apply_corrections(text: str, matches: Iterable[Match], keep: Callable[[Match], bool] = default_filter) -> str:
    filtered = [m for m in matches if keep(m)]
    return lt_correct(text, filtered)
