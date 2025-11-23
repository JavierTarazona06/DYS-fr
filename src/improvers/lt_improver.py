import os
import re
from typing import Iterable
from spacy.language import Language

from src.guardrails.entities import mask_entities, reinject_entities
from .base import TextImprover
from .lt_client import LTClient

_SAFE_CATEGORIES: set[str] = set()
_BLOCK_CATEGORIES = set() # Keep this as an empty set for now
_DEBUG_FILTER = os.getenv("LT_DEBUG_FILTER", "1").lower() in {"1", "true", "yes", "on"}

_digits_re = re.compile(r"\d")

def _category_of(match) -> str:
    try:
        cat = match.category
        if isinstance(cat, dict):
            val = cat.get("id") or cat.get("name")
        else:
            val = getattr(cat, "id", None) or getattr(cat, "name", None) or cat
        return (val or "").upper()
    except Exception:
        return ""

def _first_replacement(match) -> str | None:
    reps = match.replacements or []
    return reps[0] if reps else None

def _safe_by_category(match) -> bool:
    cat = _category_of(match)
    if any(bad in cat for bad in _BLOCK_CATEGORIES):
        return False
    if not _SAFE_CATEGORIES:
        return True
    if not cat:
        return True
    return any(good in cat for good in _SAFE_CATEGORIES)

def _does_not_add_digits(orig: str, repl: str) -> bool:
    return not (_digits_re.search(repl) and not _digits_re.search(orig))

def _token_delta_ok(orig: str, repl: str, max_delta: int = 1) -> bool: # Default value here is fine
    return (len(repl.split()) - len(orig.split())) <= max_delta


def _debug(reason: str, match, orig: str | None = None, repl: str | None = None) -> None:
    if not _DEBUG_FILTER:
        return
    try:
        print(
            f"[LT_FILTER] skip={reason} cat={_category_of(match)} rule={getattr(match, 'ruleId', None)} "
            f"msg={getattr(match, 'message', '')} orig={orig!r} repl={repl!r}"
        )
    except Exception:
        pass


def _debug_apply(match, orig: str, repl: str) -> None:
    if not _DEBUG_FILTER:
        return
    try:
        print(
            f"[LT_FILTER] apply cat={_category_of(match)} rule={getattr(match, 'ruleId', None)} "
            f"msg={getattr(match, 'message', '')} orig={orig!r} repl={repl!r}"
        )
    except Exception:
        pass

def apply_edits(text: str, edits: Iterable[tuple[int, int, str]]) -> str:
    s = text
    for off, length, repl in sorted(edits, key=lambda e: e[0], reverse=True):
        s = s[:off] + repl + s[off + length:]
    return s

class LTImprover(TextImprover):
    def __init__(
        self,
        lang: str,
        server_url: str,
        nlp: Language | None = None,
        lt_config: dict | None = None,
        passes: int = 2,
    ):
        # Pass lt_config if you intend to use it for *other* client-side LanguageTool configs
        # For 'level=picky', we are relying on the server startup args in runner.py
        self.client = LTClient(lang, server_url, config=lt_config)
        self.nlp = nlp
        self.passes = max(1, passes)

    def improve(self, text: str) -> str:
        masked = []
        text_to_check = text

        if self.nlp is not None:
            doc = self.nlp(text)
            text_to_check, masked = mask_entities(doc)

        current = text_to_check

        for _ in range(self.passes):
            matches = self.client.check(current)
            edits = []

            for m in matches:
                repl = _first_replacement(m)
                if not repl:
                    _debug("no_replacement", m)
                    continue

                if not _safe_by_category(m):
                    _debug("blocked_category", m, repl=repl)
                    continue

                orig = current[m.offset : m.offset + m.errorLength]
                if not _does_not_add_digits(orig, repl):
                    _debug("adds_digits", m, orig=orig, repl=repl)
                    continue
                # CORRECTED LINE 132 (adjust line number if other changes were made)
                if not _token_delta_ok(orig, repl, 1): # Here, simply pass the value 1
                    _debug("token_delta", m, orig=orig, repl=repl)
                    continue

                edits.append((m.offset, m.errorLength, repl))
                _debug_apply(m, orig, repl)

            if not edits:
                break

            current = apply_edits(current, edits)

        out = current

        if masked:
            out = reinject_entities(out, masked)

        return out

    def close(self):
        self.client.close()