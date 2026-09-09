"""The no-additions policy: the final gate a correction must pass before reaching the user.

This is the layer `docs/business-rules.md` has promised since October 2025 and that existed
as five `pass` stubs until 2026-09-08. It is deliberately a *whole-text* check applied after
correction, distinct from the per-replacement guards in `src/improvers/lt_improver.py`:
those filter individual LanguageTool suggestions, this one judges the finished result and is
the only thing standing between an LLM rewrite and the user.

On failure the caller returns the input unchanged. For a dyslexic reader an uncorrected
text is a small loss; a fluent text containing a date they never wrote is one they cannot
detect.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.guardrails.novelty import (
    DEFAULT_THRESHOLD,
    new_content_lemmas,
    new_out_of_vocabulary,
    novelty_ratio,
)
from src.guardrails.numbers_date import new_dates_in_docs, new_numbers_and_dates
from src.utils.text import resembles_any


@dataclass
class ValidationResult:
    passed: bool
    reason: str | None = None

    def __bool__(self) -> bool:
        return self.passed


def validate_no_new_entities(original_doc, corrected_doc) -> ValidationResult:
    """Rule A2: `NER(out) ⊆ NER(in)`.

    Compares lowercased surface forms as a multiset. Spelling fixes inside an entity are
    handled by the improvers' own guards; here an entity that has no counterpart at all is
    an invention.
    """
    original = [ent.text.lower() for ent in original_doc.ents]
    original_tokens = [token.text for token in original_doc if not token.is_punct]

    for ent in corrected_doc.ents:
        text = ent.text.lower()
        if text in original:
            original.remove(text)
        elif _entity_resembles_input(ent.text, original, original_tokens):
            continue  # "Noel" -> "Noël" is a correction, not a new entity
        else:
            return ValidationResult(False, f"new entity: {ent.text!r} ({ent.label_})")
    return ValidationResult(True)


def _entity_resembles_input(entity: str, original_entities, original_tokens) -> bool:
    """True when every word of `entity` corresponds to something the user wrote.

    Multi-word entities have to be checked word by word. Capitalising "avon" to "Avon"
    makes spaCy read the surrounding words as a person's name, and comparing the joined
    string "Nuos Avon" against individual input tokens finds nothing — so a capitalisation
    fix would be reported as an invented person. Both halves are in the input; the entity
    is not new, only newly recognised.
    """
    if resembles_any(entity, original_entities):
        return True
    words = [word for word in entity.split() if word]
    return bool(words) and all(resembles_any(word, original_tokens) for word in words)


def validate_no_new_numbers_dates(original_text, corrected_text) -> ValidationResult:
    """Rule A3: `Digits/Dates(out) ⊆ Digits/Dates(in)`."""
    added = new_numbers_and_dates(original_text, corrected_text)
    if added:
        return ValidationResult(False, f"new numbers or dates: {added}")
    return ValidationResult(True)


def validate_no_new_propn(original_doc, corrected_doc) -> ValidationResult:
    """Rule A4: no new or modified proper nouns."""
    original = [token.lemma_.lower() for token in original_doc if token.pos_ == "PROPN"]
    original_forms = {token.text.lower() for token in original_doc}

    for token in corrected_doc:
        if token.pos_ != "PROPN":
            continue
        lemma = token.lemma_.lower()
        if lemma in original:
            original.remove(lemma)
        elif token.text.lower() in original_forms:
            continue
        elif resembles_any(token.text, original_forms):
            continue  # a corrected spelling of a name the user already wrote
        else:
            return ValidationResult(False, f"new proper noun: {token.text!r}")
    return ValidationResult(True)


def validate_novelty_ratio(
    original_doc, corrected_doc, threshold: float = DEFAULT_THRESHOLD
) -> ValidationResult:
    """Rules A8/A9: the share of new content words must stay under `threshold`.

    Default 12%, decision I-1.
    """
    ratio = novelty_ratio(original_doc, corrected_doc)
    if ratio > threshold:
        added = new_content_lemmas(original_doc, corrected_doc)
        return ValidationResult(
            False, f"novelty ratio {ratio:.1%} exceeds {threshold:.0%}: {added}"
        )
    return ValidationResult(True)


def validate_no_neologisms(original_doc, corrected_doc) -> ValidationResult:
    """Rule C7: no invented or very low-frequency words the user did not write."""
    added = new_out_of_vocabulary(original_doc, corrected_doc)
    if added:
        return ValidationResult(False, f"unrecognised new words: {added}")
    return ValidationResult(True)


def validate_no_new_dates_in_docs(original_doc, corrected_doc) -> ValidationResult:
    """Rule A3, the spaCy half: DATE entities the regexes cannot see."""
    added = new_dates_in_docs(original_doc, corrected_doc)
    if added:
        return ValidationResult(False, f"new dates: {added}")
    return ValidationResult(True)


def should_accept_correction(
    original_text,
    corrected_text,
    nlp,
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> ValidationResult:
    """Run every validator. Returns the first failure, or a pass.

    Cheap checks run first so an obvious violation short-circuits before spaCy is asked to
    parse anything.
    """
    if corrected_text.strip() == original_text.strip():
        return ValidationResult(True)

    numbers = validate_no_new_numbers_dates(original_text, corrected_text)
    if not numbers.passed:
        return numbers

    original_doc = nlp(original_text)
    corrected_doc = nlp(corrected_text)

    for check in (
        validate_no_new_entities(original_doc, corrected_doc),
        validate_no_new_propn(original_doc, corrected_doc),
        validate_no_new_dates_in_docs(original_doc, corrected_doc),
        validate_no_neologisms(original_doc, corrected_doc),
        validate_novelty_ratio(original_doc, corrected_doc, threshold),
    ):
        if not check.passed:
            return check

    return ValidationResult(True)
