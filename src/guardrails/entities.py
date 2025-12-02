from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import re

from spacy.tokens import Doc, Span, Token

LOWERCASE_PARTICLES = {
    "de",
    "du",
    "des",
    "d",
    "da",
    "di",
    "la",
    "le",
    "les",
    "van",
    "von",
    "del",
    "der",
}

# Pattern to detect standalone years (e.g., 2024, 1789)
YEAR_PATTERN = re.compile(r'\b(1[0-9]{3}|20[0-9]{2})\b')


def _is_title_like(token: Token) -> bool:
    """Return True if the token looks like part of a proper name."""
    if token.pos_ == "PROPN":
        return True
    text = token.text
    if not text:
        return False
    return text[0].isupper()


def _should_mask_entity(ent: Span) -> bool:
    """
    Decide whether an entity should be masked.

    Non-PER entities are always masked. PER entities are masked only if they
    look like actual proper names; otherwise we leave them untouched so downstream
    improvers (LanguageTool, LLMs, etc.) can still correct obvious typos.
    """
    if ent.label_ != "PER":
        return True

    alpha_tokens = [tok for tok in ent if tok.is_alpha]
    if not alpha_tokens:
        return False

    required = [
        tok for tok in alpha_tokens if tok.text.lower() not in LOWERCASE_PARTICLES
    ]
    if not required:
        return False

    return all(_is_title_like(tok) for tok in required)


@dataclass(frozen=True)
class MaskedEntity:
    placeholder: str
    label: str
    start_char: int
    end_char: int
    text: str


def mask_entities(doc: Doc) -> Tuple[str, List[MaskedEntity]]:
    """
    Replace entities with neutral placeholders (ENT_{i}_{label}) while preserving offsets.
    Useful before sending text to the correction engine to avoid hallucinating or altering NER output.

    Person entities that do not look like proper names are left intact so that
    downstream tools can still fix typos.
    
    Also detects standalone years (e.g., 2024) that spaCy might have missed.
    """
    # First, collect spaCy entities
    ents_to_mask = []
    for ent in doc.ents:
        if _should_mask_entity(ent):
            ents_to_mask.append((ent.start_char, ent.end_char, ent.label_, ent.text))
    
    # Then, detect standalone years that spaCy missed
    text = doc.text
    for match in YEAR_PATTERN.finditer(text):
        year_start, year_end = match.span()
        year_text = match.group()
        
        # Check if this year is already covered by a spaCy entity
        overlap = False
        for ent_start, ent_end, _, _ in ents_to_mask:
            if not (year_end <= ent_start or year_start >= ent_end):
                overlap = True
                break
        
        if not overlap:
            ents_to_mask.append((year_start, year_end, "DATE", year_text))
    
    # Sort by start position to process in order
    ents_to_mask.sort(key=lambda e: e[0])
    
    # Build masked text
    pieces: List[str] = []
    last = 0
    masked: List[MaskedEntity] = []
    
    for start_char, end_char, label, text_val in ents_to_mask:
        pieces.append(text[last:start_char])
        placeholder = f"ENT_{len(masked)}_{label}"
        pieces.append(placeholder)
        masked.append(
            MaskedEntity(placeholder, label, start_char, end_char, text_val)
        )
        last = end_char
    
    pieces.append(text[last:])
    return "".join(pieces), masked


def reinject_entities(text_with_placeholders: str, masked: List[MaskedEntity]) -> str:
    """
    Restore each placeholder with its original text 1:1.
    Does not modify formatting, numbers, or proper nouns.
    Reversing the order of the masked entities is important to avoid shifting offsets of non replaced entities.
    """
    out = text_with_placeholders
    # Reinject in reverse order to avoid shifting offsets
    for m in reversed(masked):
        out = out.replace(m.placeholder, m.text)
    return out
