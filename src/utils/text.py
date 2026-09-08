"""Small text comparison helpers shared by the correction guards and the QA metrics.

Lives in `src/utils` rather than `src/qa` on purpose: the QA package is excluded from the
frozen bundle (`packaging/windows/dys_fr.spec`), so anything the improvers depend on has to
sit outside it.
"""

from __future__ import annotations

import unicodedata


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalise_for_comparison(text: str) -> str:
    """Lowercase, strip accents, drop everything that is not alphanumeric.

    Collapses elisions, hyphens and spacing, so "J'ai", "jai" and "j ai" compare equal.
    """
    return "".join(ch for ch in strip_accents(text.lower()) if ch.isalnum())


def within_edit_distance(a: str, b: str, limit: int) -> bool:
    """Bounded Levenshtein distance. Returns early once `limit` cannot be met."""
    if abs(len(a) - len(b)) > limit:
        return False

    previous = list(range(len(b) + 1))
    for i, ch_a in enumerate(a, start=1):
        current = [i]
        for j, ch_b in enumerate(b, start=1):
            current.append(
                previous[j - 1] if ch_a == ch_b
                else 1 + min(previous[j], current[j - 1], previous[j - 1])
            )
        if min(current) > limit:
            return False
        previous = current
    return previous[-1] <= limit
