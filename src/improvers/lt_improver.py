import os
import re
from typing import Iterable
from spacy.language import Language

from src.guardrails.entities import mask_entities, reinject_entities
from src.guardrails.policy import should_accept_correction
from src.utils.text import edit_budget, normalise_for_comparison, within_edit_distance
from .base import TextImprover
from .lt_client import LTClient

# Category-level filtering was specified (rule C8) and never worked: both sets were left
# empty, so the check allowed everything while reading like protection (TODO-3). It is
# superseded by _BLOCK_RULES below — category granularity proved too coarse, since
# PUNCTUATION as a whole carries fixes this product wants and only one of its rules is
# harmful.

# Rules whose "correction" destroys information the user put there deliberately.
# Blocked by rule id rather than by category: PUNCTUATION as a whole carries useful
# fixes, and only these specific rules are harmful.
_BLOCK_RULES = {
    # Collapses ".." or "..." into ".". Client acceptance criterion B1 requires a
    # deliberately incomplete prompt to come back still incomplete, and this rule
    # silently completes it. See TODO-10.
    "DOUBLE_PUNCTUATION",
}

def _debug_filter_enabled(environ=os.environ) -> bool:
    """Whether to trace every filtering decision. Opt-in, and it must stay that way.

    The trace quotes the user's own words (``orig``, ``repl``, LanguageTool's message). The
    frozen build redirects stdout into ``%LOCALAPPDATA%\\DYS-fr\\logs``, so an on-by-default
    trace wrote the user's text to disk on every correction (TODO-12).
    Set ``LT_DEBUG_FILTER=1`` to see it while developing.
    """
    return environ.get("LT_DEBUG_FILTER", "0").lower() in {"1", "true", "yes", "on"}


_DEBUG_FILTER = _debug_filter_enabled()

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

#: How far down LanguageTool's suggestion list to look when the first one is refused.
#: Measured on the QA corpus: 4 reaches "depuis" and "douze", both fourth; 6 also reaches
#: "Lue" for "Luer", a wrong fix, so quality has fallen off by then.
_MAX_CANDIDATES = 4

_APOSTROPHES = ("'", "’")


def _candidate_replacements(match) -> list[str]:
    """LanguageTool's suggestions, in its own order, capped at _MAX_CANDIDATES."""
    return list(match.replacements or [])[:_MAX_CANDIDATES]

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


def _stays_close_to_the_original(orig: str, repl: str) -> bool:
    """Refuse a replacement that is too far from the span it replaces to be a spelling fix.

    LanguageTool degrades badly on heavily corrupted input: the corpus caught it turning
    "montrré commen" into "m'entre nommer-en" and "kompliqué" into "complice". Those are
    rewrites, not corrections, and they reach a reader who has no way to tell.

    Judging the replacement against *its own span* is what makes this work: the whole-text
    policy layer cannot separate a good fix from a bad one, and at this granularity a
    rewrite is usually far from what it replaces while a spelling fix is not.

    Usually, not always. "depui" -> "d'appui" is two edits, the same as "preske" ->
    "presque", and passes here; _does_not_elide_into_another_word is what refuses it.

    Re-segmentation is unaffected: "unepomme" -> "une pomme" normalises to the same string.
    """
    original = normalise_for_comparison(orig)
    replacement = normalise_for_comparison(repl)
    if not original:
        return True
    return within_edit_distance(original, replacement, edit_budget(original))


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


def _does_not_elide_into_another_word(orig: str, repl: str) -> bool:
    """Allow restoring an apostrophe the user left out; refuse one that changes their word.

        "jai"   -> "j'ai"      the user's letters, with the elision restored
        "depui" -> "d'appui"   an article split off, and a different word behind it

    Distance cannot separate these. "depui" -> "d'appui" is two edits, the same as
    "preske" -> "presque", and "daans" -> "d'ans" is only one. What gives them away is the
    shape: a new apostrophe cuts the user's word in two, and a genuine elision fix does so
    without touching a single letter. Every elision-introducing replacement the QA corpus
    produced that changed letters was wrong. See TODO-13.

    The cost is an elision fix that also needs a spelling fix ("lecol" -> "l'école"); that
    word is left for the user, which is the cheaper mistake.
    """
    introduced = sum(repl.count(a) for a in _APOSTROPHES) > sum(orig.count(a) for a in _APOSTROPHES)
    if not introduced:
        return True
    return normalise_for_comparison(orig) == normalise_for_comparison(repl)


def _refusal_reason(orig: str, repl: str) -> str | None:
    """Name of the first guard that refuses this replacement, or None when all accept it.

    Guards, in order:
        _does_not_add_digits               no digit introduced
        _does_not_introduce_proper_noun    no invented capitalised word (TODO-9)
        _does_not_insert_words             no word the user never wrote (A5)
        _does_not_elide_into_another_word  no apostrophe that changes the word (TODO-13)
        _stays_close_to_the_original       a fix, not a rewrite
        _token_delta_ok                    at most one extra token
    """
    if not _does_not_add_digits(orig, repl):
        return "adds_digits"
    if not _does_not_introduce_proper_noun(orig, repl):
        return "introduces_proper_noun"
    if not _does_not_insert_words(orig, repl):
        return "inserts_words"
    if not _does_not_elide_into_another_word(orig, repl):
        return "elides_into_another_word"
    if not _stays_close_to_the_original(orig, repl):
        return "rewrite_not_correction"
    if not _token_delta_ok(orig, repl, 1):
        return "token_delta"
    return None


#: Refusals that mean "LanguageTool reached for a different kind of word", not "it does not
#: know which word this is". Only these send the search on to the next suggestion.
_WALK_PAST = {"elides_into_another_word", "introduces_proper_noun"}


def _choose_replacement(orig: str, candidates: list[str]) -> tuple[str | None, list[tuple[str, str]]]:
    """LanguageTool's best acceptable suggestion, and the ones refused on the way.

    Its first suggestion is not always its right one. For "depui" the list is
    ["d'appui", "d'étui", "d'époi", "depuis"], and for "duoze" it leads with the commune
    "d'Eauze": the spell checker ranks elided forms and place names above the plain word.
    When a suggestion is refused as that kind of invention, the next one is tried (TODO-13).

    Any other refusal ends the search with no replacement, as before. Walking past those was
    measured on the QA corpus and does harm: after a refused rewrite, the next suggestion for
    "quil" is "qui", for "mangéée" is "mangées", and after a refused insertion for "fiat" it
    is "a fiat". A spell checker whose best guess was too far off does not know the word.

    Candidates keep LanguageTool's order, so its ranking still decides.
    """
    refused = []
    for repl in candidates:
        reason = _refusal_reason(orig, repl)
        if reason is None:
            return repl, refused
        refused.append((repl, reason))
        if reason not in _WALK_PAST:
            break
    return None, refused


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
                candidates = _candidate_replacements(m)
                if not candidates:
                    _debug("no_replacement", m)
                    continue

                if not _safe_by_rule(m):
                    _debug("blocked_rule", m, repl=candidates[0])
                    continue

                orig = current[m.offset : m.offset + m.errorLength]

                # Per-replacement guards are listed in _refusal_reason. The finished text is
                # then judged as a whole by should_accept_correction below. Entity masking
                # runs before correction and validates nothing.
                chosen, refused = _choose_replacement(orig, candidates)
                for repl, reason in refused:
                    _debug(reason, m, orig=orig, repl=repl)

                if chosen is None:
                    continue

                edits.append((m.offset, m.errorLength, chosen))
                _debug_apply(m, orig, chosen)

            if not edits:
                break

            current = apply_edits(current, edits)

        out = current

        if masked:
            out = reinject_entities(out, masked)

        # Final gate. The per-replacement guards above filter individual suggestions;
        # this judges the finished text against what the user actually wrote. On failure
        # the user keeps their own words, which is the cheaper of the two mistakes.
        if self.nlp is not None:
            verdict = should_accept_correction(text, out, self.nlp)
            if not verdict.passed:
                if _DEBUG_FILTER:
                    print(f"[LT_FILTER] rejected_result reason={verdict.reason}")
                return text

        return out

    def close(self):
        self.client.close()