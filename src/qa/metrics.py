"""Metrics that define "fit for end users" in docs/business-rules.md, section H.

- H3 illegal additions must be exactly 0%
- H4 spelling and grammar errors must drop by at least 80%
- H5 mean sentence length must stay within the mode's bound
- H6 a French readability proxy must improve

The functions that do not need a language model or a running server are pure, so they can
be unit-tested directly. Only `new_entities` needs spaCy, and only `count_lt_errors` needs
the LanguageTool server.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from src.utils.text import within_edit_distance

#: Standalone numbers, including French decimal commas and ordinals like "3e".
_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?(?:\s*(?:e|er|ère|ème))?\b", re.IGNORECASE)

#: Month names carry dates that no digit check would catch.
_MONTHS = (
    "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre"
    "|novembre|décembre|decembre"
)
_DATE_WORD_RE = re.compile(rf"\b(?:{_MONTHS})\b", re.IGNORECASE)

#: Abbreviations whose full stop does not end a sentence.
_ABBREVIATIONS = ("M.", "Mme.", "Mlle.", "Dr.", "St.", "Ste.", "etc.", "cf.", "p.", "ex.")

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

_VOWELS = set("aeiouyàâäéèêëîïôöùûüÿ")


@dataclass(frozen=True)
class ReadabilityScore:
    """A proxy, not a validated readability index. Lower is easier."""

    characters_per_sentence: float
    syllables_per_sentence: float
    words_per_sentence: float


# --------------------------------------------------------------------------------------
# text structure
# --------------------------------------------------------------------------------------


def split_sentences(text: str) -> list[str]:
    """Split on sentence-final punctuation, guarding common French abbreviations.

    Deliberately simple: it feeds an aggregate metric, so an occasional bad split moves the
    mean by a fraction of a word rather than invalidating the measure.
    """
    protected = text
    for index, abbreviation in enumerate(_ABBREVIATIONS):
        protected = protected.replace(abbreviation, f"\x00{index}\x00")

    parts = [part.strip() for part in _SENTENCE_SPLIT_RE.split(protected)]

    restored = []
    for part in parts:
        for index, abbreviation in enumerate(_ABBREVIATIONS):
            part = part.replace(f"\x00{index}\x00", abbreviation)
        if part:
            restored.append(part)
    return restored


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\w'’-]+\b", text, re.UNICODE))


def count_syllables(word: str) -> int:
    """Approximate French syllable count by counting vowel groups.

    A silent final 'e' is not counted unless it would leave the word with none. This is a
    proxy indicator, which is exactly what H6 asks for.
    """
    normalised = unicodedata.normalize("NFC", word.lower())
    groups = 0
    previous_was_vowel = False
    for char in normalised:
        is_vowel = char in _VOWELS
        if is_vowel and not previous_was_vowel:
            groups += 1
        previous_was_vowel = is_vowel

    if normalised.endswith("e") and groups > 1:
        groups -= 1
    return max(groups, 1) if normalised else 0


def mean_sentence_length(text: str) -> float:
    """H5: mean words per sentence."""
    sentences = split_sentences(text)
    if not sentences:
        return 0.0
    return count_words(text) / len(sentences)


def readability(text: str) -> ReadabilityScore:
    """H6: a French readability proxy. Lower values read more easily."""
    sentences = split_sentences(text)
    if not sentences:
        return ReadabilityScore(0.0, 0.0, 0.0)

    words = re.findall(r"\b[\w'’-]+\b", text, re.UNICODE)
    syllables = sum(count_syllables(word) for word in words)
    characters = sum(len(sentence) for sentence in sentences)

    count = len(sentences)
    return ReadabilityScore(
        characters_per_sentence=characters / count,
        syllables_per_sentence=syllables / count,
        words_per_sentence=len(words) / count,
    )


# --------------------------------------------------------------------------------------
# H3 — illegal additions
# --------------------------------------------------------------------------------------


def numbers_in(text: str) -> list[str]:
    return [match.group(0).strip() for match in _NUMBER_RE.finditer(text)]


def date_words_in(text: str) -> list[str]:
    return [match.group(0).lower() for match in _DATE_WORD_RE.finditer(text)]


def new_numbers_and_dates(original: str, corrected: str) -> list[str]:
    """Numbers or date words present in the output but absent from the input.

    Multiset-aware: producing "35" twice from a single "35" is an addition, not a match.
    """
    added = []
    for extractor in (numbers_in, date_words_in):
        remaining = list(extractor(original))
        for token in extractor(corrected):
            if token in remaining:
                remaining.remove(token)
            else:
                added.append(token)
    return added


def _normalise(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _resembles_input(entity: str, input_tokens: list[str], normalised_input: str) -> bool:
    """True when something in the input plausibly corresponds to this entity.

    A correction is not an invention. Restoring the accent on "Noel" to give "Noël", or
    fixing "avon" to "avons", must not be reported as a new entity — otherwise the metric
    fires precisely when the engine does its job, and nobody trusts it.
    """
    normalised = _normalise(entity)
    if normalised in normalised_input:
        return True

    # Allow one edit per word, which covers a restored letter or a fixed ending.
    words = normalised.split()
    limit = 1 if len(normalised) <= 8 else 2
    return all(
        any(within_edit_distance(word, token, limit) for token in input_tokens)
        for word in words
    )


def new_entities(original: str, corrected: str, nlp) -> list[str]:
    """Named entities in the output that have no counterpart in the input.

    Requires a loaded spaCy pipeline. Matching is deliberately tolerant of spelling
    changes: H3 forbids *inventing* information, not correcting it.
    """
    normalised_input = _normalise(original)
    # Apostrophes are excluded from the token class on purpose: French elision means
    # "l'avon" must yield "avon", or a corrected "avons" looks invented.
    input_tokens = re.findall(r"\b[\w-]+\b", normalised_input, re.UNICODE)

    return [
        ent.text
        for ent in nlp(corrected).ents
        if not _resembles_input(ent.text, input_tokens, normalised_input)
    ]


def illegal_additions(original: str, corrected: str, nlp=None) -> dict:
    """H3. Returns the offending tokens, not just a count, so failures are diagnosable."""
    numbers_and_dates = new_numbers_and_dates(original, corrected)
    entities = new_entities(original, corrected, nlp) if nlp is not None else []
    return {
        "numbers_and_dates": numbers_and_dates,
        "entities": entities,
        "total": len(numbers_and_dates) + len(entities),
        "entities_checked": nlp is not None,
    }


# --------------------------------------------------------------------------------------
# H4 — error reduction
# --------------------------------------------------------------------------------------


def count_lt_errors(text: str, lt_client) -> int:
    """Raw LanguageTool match count.

    Deliberately raw, not the filtered hint list: TODO-1 exists because a truncated count
    was used for a comparison that needed a monotonic one.
    """
    return len(lt_client.check(text))


def error_reduction(errors_before: int, errors_after: int) -> float:
    """H4: fraction of errors removed, in [0, 1]. A clean input scores 1.0."""
    if errors_before <= 0:
        return 1.0
    return max(0.0, (errors_before - errors_after) / errors_before)
