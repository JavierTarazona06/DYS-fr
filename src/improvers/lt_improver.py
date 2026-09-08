import os
import re
from typing import Iterable
from spacy.language import Language

from src.guardrails.entities import mask_entities, reinject_entities
from src.utils.text import normalise_for_comparison, within_edit_distance
from .base import TextImprover
from .lt_client import LTClient

_SAFE_CATEGORIES: set[str] = set() # Errors to always fix
_BLOCK_CATEGORIES = set() # Keep this as an empty set for now;  Errors not to fix

# Rules whose "correction" destroys information the user put there deliberately.
# Blocked by rule id rather than by category: PUNCTUATION as a whole carries useful
# fixes, and only these specific rules are harmful.
_BLOCK_RULES = {
    # Collapses ".." or "..." into ".". Client acceptance criterion B1 requires a
    # deliberately incomplete prompt to come back still incomplete, and this rule
    # silently completes it. See TODO-10.
    "DOUBLE_PUNCTUATION",
}
_DEBUG_FILTER = os.getenv("LT_DEBUG_FILTER", "1").lower() in {"1", "true", "yes", "on"} # Debug flag

# Tokens that are always considered safe and won't be changed
_SAFE_TOKENS = {
    # Articles
    "le", "la", "les", "l", "un", "une", "des", "du", "au", "aux",
    # Common prepositions
    "de", "à", "en", "dans", "pour", "par", "avec", "sans", "sur", "sous",
    "entre", "vers", "chez", "depuis", "pendant", "avant", "après",
    # Common contractions
    "d", "j", "m", "t", "s", "n", "c", "qu", "c'est",
    # Basic conjunctions
    "et", "ou", "mais", "donc", "or", "ni", "car",
    # Common pronouns
    "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
    "me", "te", "se", "ce", "lui", "leur", "y", "en",
    # Common verbs (être, avoir conjugations)
    "suis", "es", "est", "sommes", "êtes", "sont",
    "ai", "as", "a", "avons", "avez", "ont",
    "été", "eu", "fait", "dit", "vu", "pris",
    # Common past participles
    "mangé", "acheté", "parlé", "donné", "allé", "venu", "parti",
    # Common plural forms
    "chats", "chiens", "livres", "maisons", "enfants", "amis",
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


def _safe_by_rule(match) -> bool:
    """Reject matches from rules that are never safe for this product."""
    return getattr(match, "ruleId", None) not in _BLOCK_RULES


def _does_not_introduce_proper_noun(orig: str, repl: str) -> bool:
    """Block a replacement that introduces a capitalised word absent from the original.

    LanguageTool's spell checker offers proper nouns for garbled words: the QA corpus
    caught it turning "duoze" into "Eauze", a French commune, which is exactly the
    invention the no-additions policy exists to stop. Capitalising a word the user
    already wrote ("paris" -> "Paris", "de" -> "De") is a correction and stays allowed;
    substituting a different capitalised word does not. See TODO-9.
    """
    original_normalised = normalise_for_comparison(orig)

    # Split on apostrophes and hyphens rather than scanning whole tokens: LanguageTool
    # offers elided forms, and the observed defect was "duoze" -> "d'Eauze", whose leading
    # "d" is lowercase. Checking only a token's first letter misses the invented name.
    for segment in re.split(r"[^\w]+", repl, flags=re.UNICODE):
        if len(segment) < 2 or not segment[:1].isupper():
            continue
        if normalise_for_comparison(segment) not in original_normalised:
            return False
    return True


def _does_not_insert_words(orig: str, repl: str) -> bool:
    """Allow re-segmenting the user's letters; refuse inserting a word they never wrote.

    Both cases grow the token count, so a delta bound alone cannot tell them apart:

        "unepomme" -> "une pomme"   re-segmentation, a correction a dyslexic writer needs
        "fiat"     -> "est fiat"    insertion, LanguageTool supplying a missing verb

    Stripping whitespace and punctuation separates them: a re-segmentation leaves roughly
    the same letters, an insertion does not. A small edit budget keeps a fix that both
    re-segments and corrects spelling ("unepome" -> "une pomme") on the allowed side.

    Rule A5 forbids adding meaning-bearing words; before this guard it was enforced only
    by asking the LLM nicely, and not at all in light mode.
    """
    if len(repl.split()) <= len(orig.split()):
        return True

    original = normalise_for_comparison(orig)
    replacement = normalise_for_comparison(repl)
    budget = 1 if len(original) <= 8 else 2
    return within_edit_distance(original, replacement, budget)


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

                if not _safe_by_rule(m):
                    _debug("blocked_rule", m, repl=repl)
                    continue

                orig = current[m.offset : m.offset + m.errorLength]

                # The whitelist check (_is_whitelist_change) is deliberately not called: it
                # blocked legitimate corrections like "sui"->"suis" and "chat"->"chats".
                # The guards that actually run on every replacement are, in order:
                #   _safe_by_rule                  blocked rule ids (TODO-10)
                #   _does_not_add_digits           no digit introduced
                #   _does_not_introduce_proper_noun  no invented capitalised word (TODO-9)
                #   _does_not_insert_words         no word the user never wrote (A5)
                #   _token_delta_ok                at most one extra token
                # Note what is *not* here: entity masking happens before correction and does
                # not validate the result, and _safe_by_category is inert while both
                # category sets are empty (TODO-3).

                if not _does_not_add_digits(orig, repl):
                    _debug("adds_digits", m, orig=orig, repl=repl)
                    continue

                if not _does_not_introduce_proper_noun(orig, repl):
                    _debug("introduces_proper_noun", m, orig=orig, repl=repl)
                    continue

                if not _does_not_insert_words(orig, repl):
                    _debug("inserts_words", m, orig=orig, repl=repl)
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