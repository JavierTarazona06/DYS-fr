"""Novelty ratio: how much new meaning a correction introduced.

Rule A8/A9. The threshold is **12%**, decision I-1, taken from the DYS-specific engine
document which chose the stricter of the three figures in circulation. For this audience a
false rejection — returning the user's own text unchanged — costs far less than an accepted
hallucination the reader cannot detect.

Only content words count. Function words move around freely during legitimate correction
(articles, prepositions, elisions), and counting them would make the ratio noise.
"""

from __future__ import annotations

from collections import Counter

from src.guardrails.alignment import corrections_of_user_words
from src.utils.text import resembles_any

#: Parts of speech that carry meaning. A new one of these is new information.
CONTENT_POS = frozenset({"NOUN", "VERB", "ADJ", "ADV", "PROPN", "NUM"})

#: Decision I-1.
DEFAULT_THRESHOLD = 0.12


def _content_tokens(doc):
    """(lemma, surface form, token index) for every content word, lemma and form lowercased.

    Both are needed: correcting "parton" to "partons" moves the lemma from the unrecognised
    form to "partir", two edits away, while the surface forms are one edit apart. Comparing
    lemmas alone would call a routine conjugation fix a new word.
    """
    return [
        (token.lemma_.lower(), token.text.lower(), token.i)
        for token in doc
        if token.pos_ in CONTENT_POS and not token.is_space and not token.is_punct
    ]


def content_lemmas(doc) -> list[str]:
    """Lowercased lemmas of the content words in a spaCy doc."""
    return [lemma for lemma, _, _ in _content_tokens(doc)]


def new_content_lemmas(original_doc, corrected_doc) -> list[str]:
    """Content lemmas the correction introduced, counted as a multiset.

    Saying "chat" twice where the user said it once introduces one new lemma occurrence,
    which is the behaviour a ratio needs.

    A lemma that merely *resembles* one in the original is not new: correcting
    "supermarchet" to "supermarché" changes the lemma, and without this tolerance the
    ratio would reject every spelling fix the product exists to make.

    Nor is a word that stands in the place of one the user wrote and sounds like it, or
    shares its stem. Phonetic writing is far from its word in spelling — "koman" ->
    "comment" is four edits — and without this the ratio refused faithful corrections of
    exactly the writing hybrid mode exists for (TODO-21). The comparison is aligned: an
    *inserted* word is never excused this way. Measured by inserting 40 common words into
    each corpus text, applying sound tolerance against the whole text instead let 127 of
    1,140 insertions through that are caught now.
    """
    original_lemmas = content_lemmas(original_doc)
    remaining = Counter(original_lemmas)

    # Every form the user actually typed, content word or not: a word can change part of
    # speech when it is corrected.
    original_forms = [token.text for token in original_doc if not token.is_punct]
    known = original_lemmas + original_forms
    corrections = corrections_of_user_words(original_doc, corrected_doc)

    added: list[str] = []
    for lemma, form, index in _content_tokens(corrected_doc):
        if remaining[lemma] > 0:
            remaining[lemma] -= 1
        elif resembles_any(lemma, known) or resembles_any(form, known):
            continue
        elif index in corrections:
            continue
        else:
            added.append(lemma)
    return added


def novelty_ratio(original_doc, corrected_doc) -> float:
    """Fraction of the corrected text's content words that are new, in [0, 1].

    A correction that only fixes spelling scores 0, because lemmatisation maps the fixed
    form back onto the same lemma. An empty correction scores 0 rather than dividing by
    zero.
    """
    corrected = content_lemmas(corrected_doc)
    if not corrected:
        return 0.0
    return len(new_content_lemmas(original_doc, corrected_doc)) / len(corrected)


def new_out_of_vocabulary(original_doc, corrected_doc) -> list[str]:
    """New content words spaCy does not recognise — the neologism check of rule C7.

    `is_oov` is a proxy for "not a frequent French word". It is not a frequency lexicon,
    but it reliably separates invented forms ("flurbait", "zorglub") from real vocabulary,
    which is what C7 is trying to stop.
    """
    original_lemmas = set(content_lemmas(original_doc))
    original_forms = {token.text.lower() for token in original_doc}

    return [
        token.text
        for token in corrected_doc
        if token.pos_ in CONTENT_POS
        and token.is_alpha
        and token.is_oov
        and token.lemma_.lower() not in original_lemmas
        and token.text.lower() not in original_forms
    ]
