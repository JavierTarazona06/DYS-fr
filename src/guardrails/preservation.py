"""Lost words: the meaning a correction removed.

The counterpart of `novelty.py`. The no-additions policy asks what a correction put in; this
asks what it took out. Both change what the text says, and a reader who trusts the output
cannot see either. Found as TODO-14: the hybrid mode turned "Je sui aller au magasin." into
"Je suis au magasin.", and every other guard passed it — the verb was gone, nothing was
added, and the shorter sentence even had fewer LanguageTool errors.

A word the user wrote counts as kept when the stretch of output that replaced it respells,
reinflects, merges or splits it — by spelling, sound or stem. The comparisons live in
`alignment.py`, which the novelty guard shares. A deletion leaves nothing in its place, and
a substitution — "quartier" -> "monde" — leaves a different word.

Measured on 2026-09-17 against 109 light-mode corrections and 39 hybrid-mode outputs: no
light-mode correction refused, and 10 hybrid outputs refused, every one of which dropped or
swapped a word — five of them had passed every other guard. A shared stem is also the known
blind spot: a substitution that starts like the user's word ("quartier" -> "quartz") passes.

Only content words count, as in the novelty ratio. Articles and prepositions come and go in
legitimate corrections ("de le" -> "du").
"""

from __future__ import annotations

from src.guardrails.alignment import blocks, recognised, words
from src.guardrails.novelty import CONTENT_POS


def _is_content(word: dict) -> bool:
    # Stop words are excluded even when tagged as content: "va" or "même" carry little
    # meaning, and spaCy tags them inconsistently on misspelt input.
    return word["pos"] in CONTENT_POS and not word["is_stop"]


def lost_content_words(original_doc, corrected_doc) -> list[str]:
    """Content words the user wrote that the correction removed or replaced with another word.

    A word still counts as present when it appears anywhere in the output with the same
    letters, so a removed duplication ("la maison maison") or a moved word is not a loss.
    Reordering is not this check's concern.
    """
    original = words(original_doc)
    corrected = words(corrected_doc)
    anywhere = {word["form"] for word in corrected}

    lost: list[str] = []
    for operation, i1, i2, j1, j2 in blocks(original, corrected):
        if operation in ("equal", "insert"):
            continue
        block = original[i1:i2]
        kept = recognised(block, corrected[j1:j2])
        lost.extend(
            word["text"]
            for index, word in enumerate(block)
            if _is_content(word) and index not in kept and word["form"] not in anywhere
        )
    return lost
