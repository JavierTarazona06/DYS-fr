"""Error injectors for the QA corpus, organised by the published taxonomy.

Research on French-speaking children with dyslexia classifies spelling errors into three
families — phonological, visuo-orthographic and morphological. The corpus is built on that
taxonomy rather than on an invented list, so the resulting metrics are defensible: each
injected error can be traced to a category the literature actually measures.

The project's own documented patterns (letter inversions, duplications, omitted accents,
frequent homophones) are not a separate scheme; they are concrete instances that sit inside
these categories, and are labelled as such below.

Every injector is deterministic given the same text and Random instance, so a corpus
generated from a fixed seed is reproducible and diffable across runs.
"""

from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Callable


class ErrorCategory(str, Enum):
    """The three families used to classify dyslexic spelling errors."""

    PHONOLOGICAL = "phonological"
    VISUO_ORTHOGRAPHIC = "visuo_orthographic"
    MORPHOLOGICAL = "morphological"


@dataclass(frozen=True)
class InjectedError:
    """One applied error, kept so the corpus carries its own ground truth."""

    injector_id: str
    category: ErrorCategory
    original: str
    replacement: str


@dataclass(frozen=True)
class Injector:
    id: str
    category: ErrorCategory
    description: str
    apply: Callable[[str, random.Random], tuple[str, InjectedError | None]]


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------

_WORD_RE = re.compile(r"\b[A-Za-zÀ-ÖØ-öø-ÿ]{3,}\b")


def _iter_word_spans(text: str):
    """Yield (start, end, word) for candidate words, longest first for stability."""
    return [(m.start(), m.end(), m.group(0)) for m in _WORD_RE.finditer(text)]


def _replace_span(text: str, start: int, end: int, replacement: str) -> str:
    return text[:start] + replacement + text[end:]


def _pick(rng: random.Random, items: list):
    return items[rng.randrange(len(items))] if items else None


def _strip_accents(word: str) -> str:
    decomposed = unicodedata.normalize("NFD", word)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _preserve_case(source: str, replacement: str) -> str:
    if source.isupper():
        return replacement.upper()
    if source[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


# --------------------------------------------------------------------------------------
# phonological — the written form does not recover the right sounds
# --------------------------------------------------------------------------------------

#: Project pattern: "inversions de lettres typiques (oi<->io, eu<->ue)".
_INVERSION_PAIRS = [("oi", "io"), ("eu", "ue"), ("ou", "uo"), ("ai", "ia")]


def _invert_letter_pair(text: str, rng: random.Random) -> tuple[str, InjectedError | None]:
    candidates = [
        (start, end, word, a, b)
        for start, end, word in _iter_word_spans(text)
        for a, b in _INVERSION_PAIRS
        if a in word.lower()
    ]
    chosen = _pick(rng, candidates)
    if chosen is None:
        return text, None
    start, end, word, a, b = chosen
    replacement = word.replace(a, b, 1) if a in word else word.replace(a.upper(), b.upper(), 1)
    return _replace_span(text, start, end, replacement), InjectedError(
        "letter_inversion", ErrorCategory.PHONOLOGICAL, word, replacement
    )


#: Substitutions that keep the sound roughly but break the spelling.
_PHONETIC_SUBSTITUTIONS = [("ph", "f"), ("qu", "k"), ("ss", "s"), ("c", "k"), ("gn", "ni")]


def _phonetic_substitution(text: str, rng: random.Random) -> tuple[str, InjectedError | None]:
    candidates = [
        (start, end, word, a, b)
        for start, end, word in _iter_word_spans(text)
        for a, b in _PHONETIC_SUBSTITUTIONS
        if a in word.lower() and len(word) > 3
    ]
    chosen = _pick(rng, candidates)
    if chosen is None:
        return text, None
    start, end, word, a, b = chosen
    replacement = word.lower().replace(a, b, 1)
    replacement = _preserve_case(word, replacement)
    return _replace_span(text, start, end, replacement), InjectedError(
        "phonetic_substitution", ErrorCategory.PHONOLOGICAL, word, replacement
    )


def _drop_silent_ending(text: str, rng: random.Random) -> tuple[str, InjectedError | None]:
    """Omit a silent final consonant, a hallmark phonological error."""
    candidates = [
        (start, end, word)
        for start, end, word in _iter_word_spans(text)
        if len(word) > 4 and word[-1].lower() in "tdsxz"
    ]
    chosen = _pick(rng, candidates)
    if chosen is None:
        return text, None
    start, end, word = chosen
    replacement = word[:-1]
    return _replace_span(text, start, end, replacement), InjectedError(
        "silent_ending_dropped", ErrorCategory.PHONOLOGICAL, word, replacement
    )


# --------------------------------------------------------------------------------------
# visuo-orthographic — plausible sounds, wrong spelling
# --------------------------------------------------------------------------------------


def _drop_accent(text: str, rng: random.Random) -> tuple[str, InjectedError | None]:
    """Project pattern: "accent manquant"."""
    candidates = [
        (start, end, word)
        for start, end, word in _iter_word_spans(text)
        if _strip_accents(word) != word
    ]
    chosen = _pick(rng, candidates)
    if chosen is None:
        return text, None
    start, end, word = chosen
    replacement = _strip_accents(word)
    return _replace_span(text, start, end, replacement), InjectedError(
        "accent_dropped", ErrorCategory.VISUO_ORTHOGRAPHIC, word, replacement
    )


def _duplicate_letter(text: str, rng: random.Random) -> tuple[str, InjectedError | None]:
    """Project pattern: "duplications" ("llll")."""
    candidates = [
        (start, end, word) for start, end, word in _iter_word_spans(text) if len(word) > 3
    ]
    chosen = _pick(rng, candidates)
    if chosen is None:
        return text, None
    start, end, word = chosen
    index = rng.randrange(1, len(word) - 1)
    replacement = word[:index] + word[index] + word[index:]
    return _replace_span(text, start, end, replacement), InjectedError(
        "letter_duplicated", ErrorCategory.VISUO_ORTHOGRAPHIC, word, replacement
    )


#: Project pattern: "homophones fréquents". Pairs whose confusion is purely orthographic.
_ORTHOGRAPHIC_HOMOPHONES = [
    ("et", "est"), ("est", "et"),
    ("ou", "où"), ("où", "ou"),
    ("ce", "se"), ("se", "ce"),
    ("la", "là"), ("là", "la"),
    ("ces", "ses"), ("ses", "ces"),
]


def _confuse_homophone(text: str, rng: random.Random) -> tuple[str, InjectedError | None]:
    candidates = []
    for start, end, word in _iter_word_spans(text):
        for source, target in _ORTHOGRAPHIC_HOMOPHONES:
            if word.lower() == source:
                candidates.append((start, end, word, target))
    chosen = _pick(rng, candidates)
    if chosen is None:
        return text, None
    start, end, word, target = chosen
    replacement = _preserve_case(word, target)
    return _replace_span(text, start, end, replacement), InjectedError(
        "homophone_confusion", ErrorCategory.VISUO_ORTHOGRAPHIC, word, replacement
    )


# --------------------------------------------------------------------------------------
# morphological — agreement and inflection
# --------------------------------------------------------------------------------------

#: The é / er / ez confusion is the canonical French morphological error.
_VERB_ENDINGS = [("é", "er"), ("er", "é"), ("é", "ez"), ("ée", "er")]


def _confuse_verb_ending(text: str, rng: random.Random) -> tuple[str, InjectedError | None]:
    candidates = [
        (start, end, word, a, b)
        for start, end, word in _iter_word_spans(text)
        for a, b in _VERB_ENDINGS
        if word.lower().endswith(a) and len(word) > 3
    ]
    chosen = _pick(rng, candidates)
    if chosen is None:
        return text, None
    start, end, word, a, b = chosen
    replacement = word[: len(word) - len(a)] + b
    return _replace_span(text, start, end, replacement), InjectedError(
        "verb_ending_confusion", ErrorCategory.MORPHOLOGICAL, word, replacement
    )


#: Homophone pairs whose confusion is an agreement error, not just a spelling one.
_AGREEMENT_HOMOPHONES = [
    ("son", "sont"), ("sont", "son"),
    ("on", "ont"), ("ont", "on"),
    ("a", "à"), ("à", "a"),
]


def _confuse_agreement_homophone(text: str, rng: random.Random) -> tuple[str, InjectedError | None]:
    candidates = []
    for start, end, word in _iter_word_spans(text):
        for source, target in _AGREEMENT_HOMOPHONES:
            if word.lower() == source:
                candidates.append((start, end, word, target))
    chosen = _pick(rng, candidates)
    if chosen is None:
        return text, None
    start, end, word, target = chosen
    replacement = _preserve_case(word, target)
    return _replace_span(text, start, end, replacement), InjectedError(
        "agreement_homophone", ErrorCategory.MORPHOLOGICAL, word, replacement
    )


#: Words ending in -s that are not plurals. Dropping their -s is a real dyslexic error, but
#: it is not a *morphological* one, and mislabelling it would weaken the category counts.
_NOT_PLURALS = {
    "trois", "puis", "depuis", "toujours", "jamais", "alors", "après", "très",
    "plus", "moins", "sans", "dans", "vers", "sous", "mais", "temps", "corps",
    "fois", "souris", "tapis", "repas", "bras", "pays", "mois",
}


def _drop_plural_mark(text: str, rng: random.Random) -> tuple[str, InjectedError | None]:
    candidates = [
        (start, end, word)
        for start, end, word in _iter_word_spans(text)
        if len(word) > 4
        and word.lower().endswith("s")
        and not word.lower().endswith("ss")
        and word.lower() not in _NOT_PLURALS
    ]
    chosen = _pick(rng, candidates)
    if chosen is None:
        return text, None
    start, end, word = chosen
    replacement = word[:-1]
    return _replace_span(text, start, end, replacement), InjectedError(
        "plural_mark_dropped", ErrorCategory.MORPHOLOGICAL, word, replacement
    )


# --------------------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------------------

INJECTORS: tuple[Injector, ...] = (
    Injector("letter_inversion", ErrorCategory.PHONOLOGICAL,
             "Typical oi/io, eu/ue letter inversion", _invert_letter_pair),
    Injector("phonetic_substitution", ErrorCategory.PHONOLOGICAL,
             "Phonetically plausible substitution (ph->f, qu->k)", _phonetic_substitution),
    Injector("silent_ending_dropped", ErrorCategory.PHONOLOGICAL,
             "Omitted silent final consonant", _drop_silent_ending),
    Injector("accent_dropped", ErrorCategory.VISUO_ORTHOGRAPHIC,
             "Omitted diacritic", _drop_accent),
    Injector("letter_duplicated", ErrorCategory.VISUO_ORTHOGRAPHIC,
             "Duplicated letter", _duplicate_letter),
    Injector("homophone_confusion", ErrorCategory.VISUO_ORTHOGRAPHIC,
             "Frequent homophone confusion (et/est, ou/ou, ce/se)", _confuse_homophone),
    Injector("verb_ending_confusion", ErrorCategory.MORPHOLOGICAL,
             "The e-acute / -er / -ez verb ending confusion", _confuse_verb_ending),
    Injector("agreement_homophone", ErrorCategory.MORPHOLOGICAL,
             "Homophone confusion that breaks agreement (son/sont, on/ont, a/a-grave)",
             _confuse_agreement_homophone),
    Injector("plural_mark_dropped", ErrorCategory.MORPHOLOGICAL,
             "Omitted plural marker", _drop_plural_mark),
)

INJECTORS_BY_ID = {injector.id: injector for injector in INJECTORS}


def injectors_for(category: ErrorCategory) -> tuple[Injector, ...]:
    return tuple(injector for injector in INJECTORS if injector.category is category)
