import os
import re
from typing import Iterable
from spacy.language import Language

from src.guardrails.entities import mask_entities, reinject_entities
from .base import TextImprover
from .lt_client import LTClient

_SAFE_CATEGORIES: set[str] = set() # Errors to always fix
_BLOCK_CATEGORIES = set() # Keep this as an empty set for now;  Errors not to fix
_DEBUG_FILTER = os.getenv("LT_DEBUG_FILTER", "1").lower() in {"1", "true", "yes", "on"} # Debug flag

# Tokens that are always considered safe and won't be changed
_SAFE_TOKENS = {
    # Articles
    "le", "la", "les", "l", "un", "une", "des", "du", "au", "aux",
    # Common prepositions
    "de", "à", "en", "dans", "pour", "par", "avec", "sans", "sur", "sous",
    "entre", "vers", "chez", "depuis", "pendant", "avant", "après",
    # Common contractions
    "d", "j", "m", "t", "s", "n", "c", "qu",
    # Basic conjunctions
    "et", "ou", "mais", "donc", "or", "ni", "car",
    # Common pronouns
    "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
    "me", "te", "se", "ce", "lui", "leur", "y", "en",
    # Punctuation and symbols
    ",", ".", ";", ":", "?", "!", "'", "-", "...",
}

_digits_re = re.compile(r"\d")

# Helper functions for filtering LT matches

def _category_of(match) -> str:
    """Get the category of the match in uppercase. From LT errors category"""
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
    """Get the first replacement suggestion from the match"""
    reps = match.replacements or []
    return reps[0] if reps else None

def _safe_by_category(match) -> bool:
    """Determine if the match category is considered safe"""
    cat = _category_of(match)
    if any(bad in cat for bad in _BLOCK_CATEGORIES):
        return False # Blocked category, error should not be fixed
    if not _SAFE_CATEGORIES:
        return True # If no safe categories defined, allow all
    if not cat:
        return True # No category info, allow
    return any(good in cat for good in _SAFE_CATEGORIES)

 #TODO: However it can change the  digit, we need to block it ?
def _does_not_add_digits(orig: str, repl: str) -> bool:
    """Check if the replacement does not add digits compared to the original"""
    return not (_digits_re.search(repl) and not _digits_re.search(orig))

def _token_delta_ok(orig: str, repl: str, max_delta: int = 1) -> bool: # Default value here is fine
    """Check if the token count difference between original and replacement is within max_delta."""
    return (len(repl.split()) - len(orig.split())) <= max_delta


def _is_whitelist_change(orig: str, repl: str) -> bool:
    """
    Check if the change only involves tokens from the whitelist.
    Returns True if all new or modified tokens are in the safe token set.
    """
    orig_tokens = {t.lower() for t in orig.split() if t.strip()}
    repl_tokens = {t.lower() for t in repl.split() if t.strip()}
    
    # Tokens that were added or modified
    new_tokens = repl_tokens - orig_tokens
    
    # If there are no new tokens, it's safe (only deletion)
    if not new_tokens:
        return True
    
    # Verify that all new tokens are in the safe set
    return all(token in _SAFE_TOKENS for token in new_tokens)

def _debug(reason: str, match, orig: str | None = None, repl: str | None = None) -> None:
    # Debugging output for filtering decisions
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
    # Debugging output for applied edits
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
    #  Apply a series of edits to the text
    s = text
    for off, length, repl in sorted(edits, key=lambda e: e[0], reverse=True):
        s = s[:off] + repl + s[off + length:]
    return s

class LTImprover(TextImprover):
    # LanguageTool-based text improver with entity masking and filtering
    def __init__(
        self,
        lang: str,
        server_url: str,
        nlp: Language | None = None, # Spacy NLP pipeline for entity masking
        lt_config: dict | None = None, # Client-side LT config (if any)
        passes: int = 2, # Number of improvement passes
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

                # Verify whitelist changes
                if not _is_whitelist_change(orig, repl):
                    _debug("not_whitelist", m, orig=orig, repl=repl)
                    continue

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