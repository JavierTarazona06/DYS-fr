"""Small text comparison helpers shared by the correction guards and the QA metrics.

Lives in `src/utils` rather than `src/qa` on purpose: the QA package is excluded from the
frozen bundle (`packaging/windows/dys_fr.spec`), so anything the improvers depend on has to
sit outside it.
"""

from __future__ import annotations

import re
import unicodedata


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalise_for_comparison(text: str) -> str:
    """Lowercase, strip accents, drop everything that is not alphanumeric.

    Collapses elisions, hyphens and spacing, so "J'ai", "jai" and "j ai" compare equal.
    """
    return "".join(ch for ch in strip_accents(text.lower()) if ch.isalnum())


#: Ordered rewrites from French spelling to a rough sound key. Later rules see the output
#: of earlier ones, so the order matters: "ch" must reach the "h" rule already as "kh".
_SOUND_RULES = [
    (re.compile(r"eau|au"), "o"),
    (re.compile(r"ph"), "f"),
    (re.compile(r"qu|ck|q"), "k"),
    (re.compile(r"c(?=[eiy])"), "s"),
    (re.compile(r"c"), "k"),
    (re.compile(r"g(?=[eiy])"), "j"),
    (re.compile(r"gu(?=[eiy])"), "g"),
    (re.compile(r"th"), "t"),
    (re.compile(r"(?<!c|s)h"), ""),
    (re.compile(r"oi"), "wa"),
    (re.compile(r"ou"), "u"),
    (re.compile(r"ai|ei"), "e"),
    (re.compile(r"(?:en|an|em|am)(?![aeiouy])"), "A"),
    (re.compile(r"(?:on|om)(?![aeiouy])"), "O"),
    (re.compile(r"(?:ain|ein|in|im|un)(?![aeiouy])"), "I"),
    (re.compile(r"y"), "i"),
    (re.compile(r"(?:er|ez|et)$"), "e"),
    (re.compile(r"([a-z])\1"), r"\1"),
    (re.compile(r"(?<=[aeiou])s(?=[aeiou])"), "z"),
]
_SILENT_ENDING = re.compile(r"[estdxzp]+$")


def sound_key(word: str) -> str:
    """A rough key for how a French word sounds, so phonetic spellings match their word.

    Dyslexic writing is largely phonetic: "kom" for "comme", "koman" for "comment",
    "otomobil" for "automobile". Those are four edits apart in spelling and next to nothing
    apart in sound, and a guard that compares spelling alone mistakes their correction for a
    different word.

    Deliberately rough — a few ordered rules, not a phonetisation. It only has to bring a
    phonetic misspelling within an edit or two of its correction; it is never used to decide
    what a word *is*. Digits and punctuation drop out, so a number has an empty key.
    """
    w = strip_accents(word.lower().replace("ç", "s"))
    w = "".join(ch for ch in w if "a" <= ch <= "z")
    for pattern, replacement in _SOUND_RULES:
        w = pattern.sub(replacement, w)
    return _SILENT_ENDING.sub("", w) or w


def edit_budget(text: str) -> int:
    """How many edits still count as "the same word, spelled differently".

    Calibrated against the errors this product actually sees. A phonetic substitution like
    "preske" -> "presque" costs two edits on a seven-letter word, so a budget of one would
    refuse the correction of an error the corpus deliberately injects. Three edits are
    allowed on long words, where a dyslexic spelling often carries several.

    The ceiling still holds where it matters: "duoze" -> "Eauze", the invented commune the
    corpus caught, is three edits on a five-letter word and stays out of budget.
    """
    if len(text) <= 4:
        return 1
    if len(text) <= 10:
        return 2
    return 3


def resembles_any(word: str, candidates) -> bool:
    """True when `word` is a plausible correction of one of `candidates`.

    This is what keeps the no-additions guards from rejecting the product's own work.
    "supermarchet" -> "supermarché" and "Noel" -> "Noël" are corrections, not inventions,
    and a guard that cannot tell the difference refuses every fix the tool makes.
    """
    normalised = normalise_for_comparison(word)
    if not normalised:
        return True
    budget = edit_budget(normalised)
    return any(
        within_edit_distance(normalised, normalise_for_comparison(candidate), budget)
        for candidate in candidates
    )


def within_edit_distance(a: str, b: str, limit: int) -> bool:
    """Bounded Damerau-Levenshtein distance (optimal string alignment).

    Transposition counts as **one** edit, not two. That is not a refinement, it is the
    point: letter inversion is the signature dyslexic error — "trian" for "train",
    "juors" for "jours" — and plain Levenshtein charges two for it, which would make the
    guards refuse to recognise the correction of the very errors this product targets.

    Returns early once `limit` can no longer be met.
    """
    if abs(len(a) - len(b)) > limit:
        return False

    # Row -1 is only needed for the transposition term.
    before_previous: list[int] | None = None
    previous = list(range(len(b) + 1))

    for i, ch_a in enumerate(a, start=1):
        current = [i]
        for j, ch_b in enumerate(b, start=1):
            cost = 0 if ch_a == ch_b else 1
            value = min(
                previous[j] + 1,          # deletion
                current[j - 1] + 1,       # insertion
                previous[j - 1] + cost,   # substitution
            )
            if (
                before_previous is not None
                and i > 1
                and j > 1
                and ch_a == b[j - 2]
                and a[i - 2] == ch_b
            ):
                value = min(value, before_previous[j - 2] + 1)  # transposition
            current.append(value)

        if min(current) > limit:
            return False
        before_previous, previous = previous, current

    return previous[-1] <= limit
