"""Extraction and comparison of numbers and dates.

Rule A3: `Digits/Dates(out) ⊆ Digits/Dates(in)`. A correction may fix how a number is
spelled, but the tool must never produce a figure or a date the user did not write — that
is the failure a dyslexic reader is least able to catch, because the text still reads
fluently.

Comparison is multiset-aware: turning one "35" into two is an addition, not a match.
"""

from __future__ import annotations

import re

from src.utils.text import resembles_any

#: Standalone numbers, including French decimal commas and ordinals ("3e", "1er").
_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?(?:\s*(?:e|er|ère|ème))?\b", re.IGNORECASE)

#: Month names carry dates that no digit check would catch.
_MONTHS = (
    "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre"
    "|novembre|décembre|decembre"
)
_DATE_WORD_RE = re.compile(rf"\b(?:{_MONTHS})\b", re.IGNORECASE)

#: Spelled-out numbers a spell checker could plausibly invent or alter.
_NUMBER_WORDS = (
    "zéro|zero|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize"
    "|quatorze|quinze|seize|vingt|trente|quarante|cinquante|soixante|cent|mille"
)
_NUMBER_WORD_RE = re.compile(rf"\b(?:{_NUMBER_WORDS})\b", re.IGNORECASE)


def numbers_in(text: str) -> list[str]:
    """Digit-bearing numbers, normalised of surrounding whitespace."""
    return [match.group(0).strip() for match in _NUMBER_RE.finditer(text)]


def date_words_in(text: str) -> list[str]:
    return [match.group(0).lower() for match in _DATE_WORD_RE.finditer(text)]


def number_words_in(text: str) -> list[str]:
    return [match.group(0).lower() for match in _NUMBER_WORD_RE.finditer(text)]


def dates_in_doc(doc) -> list[str]:
    """DATE entities, which catch forms the regexes miss ("le lendemain", "l'été dernier").

    The pipeline installs a date ruler (`src/guardrails/spacy_loader.py`), so this is
    richer than the month regex alone.
    """
    return [ent.text.lower() for ent in doc.ents if ent.label_ == "DATE"]


def _added(original_items: list[str], corrected_items: list[str]) -> list[str]:
    """Items in the corrected list with no counterpart left in the original."""
    remaining = list(original_items)
    added = []
    for item in corrected_items:
        if item in remaining:
            remaining.remove(item)
        else:
            added.append(item)
    return added


def new_numbers_and_dates(original: str, corrected: str) -> list[str]:
    """Numbers, number words or date words the correction introduced.

    Digits are compared strictly: "2" and "3" are one edit apart, and tolerating that would
    defeat the whole rule. Spelled-out numbers and month names are compared with the same
    correction tolerance as the rest of the guards, because they are ordinary words that get
    misspelled — the corpus caught "kinq" being correctly fixed to "cinq" and reported as an
    invented number.
    """
    added: list[str] = list(_added(numbers_in(original), numbers_in(corrected)))

    original_tokens = re.findall(r"[\w'’-]+", original, re.UNICODE)
    for extractor in (date_words_in, number_words_in):
        for token in _added(extractor(original), extractor(corrected)):
            if not resembles_any(token, original_tokens):
                added.append(token)
    return added


def new_dates_in_docs(original_doc, corrected_doc) -> list[str]:
    """DATE entities the correction introduced, using spaCy rather than regexes."""
    return _added(dates_in_doc(original_doc), dates_in_doc(corrected_doc))
