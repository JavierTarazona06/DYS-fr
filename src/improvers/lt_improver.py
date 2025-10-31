import re
from typing import Iterable
from .base import TextImprover
from .lt_client import LTClient

_SAFE_CATEGORIES = {
    "TYPOS", "TYPOGRAPHY", "PUNCTUATION", "GRAMMAR", "CASING", "CONFUSED_WORDS"
}
_BLOCK_CATEGORIES = {"STYLE", "CLARITY", "REDUNDANCY"}

_digits_re = re.compile(r"\d")

def _category_of(match) -> str:
    # language_tool_python Match.category is an object with .name usually
    try:
        name = (match.category or {}).get("name") if isinstance(match.category, dict) else match.category
        return (name or "").upper()
    except Exception:
        return ""

def _first_replacement(match) -> str | None:
    reps = match.replacements or []
    return reps[0] if reps else None

def _safe_by_category(match) -> bool:
    cat = _category_of(match)
    if any(bad in cat for bad in _BLOCK_CATEGORIES):
        return False
    if _SAFE_CATEGORIES and not any(good in cat for good in _SAFE_CATEGORIES):
        # If LT returns unexpected categories, be conservative
        return False
    return True

def _does_not_add_digits(orig: str, repl: str) -> bool:
    # Block edits that introduce digits (dates, numbers)
    return not (_digits_re.search(repl) and not _digits_re.search(orig))

def _token_delta_ok(orig: str, repl: str, max_delta: int = 1) -> bool:
    return (len(repl.split()) - len(orig.split())) <= max_delta

def apply_edits(text: str, edits: Iterable[tuple[int, int, str]]) -> str:
    """
    Apply non-overlapping (offset, length, replacement) edits right-to-left.
    """
    s = text
    for off, length, repl in sorted(edits, key=lambda e: e[0], reverse=True):
        s = s[:off] + repl + s[off + length:]
    return s

class LTImprover(TextImprover):
    """
    LanguageTool-based improver with conservative DYS-safe filtering.
    (You will add post-guardrails with spaCy in guardrails/policy.py later.)
    """
    def __init__(self, lang: str, server_url: str):
        self.client = LTClient(lang, server_url)

    def improve(self, text: str) -> str:
        matches = self.client.check(text)
        edits = []

        for m in matches:
            repl = _first_replacement(m)
            if not repl:
                continue

            if not _safe_by_category(m):
                continue

            orig = text[m.offset : m.offset + m.errorLength]
            if not _does_not_add_digits(orig, repl):
                continue
            if not _token_delta_ok(orig, repl, max_delta=1):
                continue

            edits.append((m.offset, m.errorLength, repl))

        if not edits:
            return text

        out = apply_edits(text, edits)
        return out

    def close(self):
        self.client.close()
