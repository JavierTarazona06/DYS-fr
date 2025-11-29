from dataclasses import dataclass
from typing import Set

@dataclass
class ValidationResult:
    passed: bool
    reason: str | None = None
    
def validate_no_new_entities(original_doc, corrected_doc) -> ValidationResult:
    """Verifica NER(out) ⊆ NER(in)"""
    pass

def validate_no_new_numbers_dates(original_text, corrected_text) -> ValidationResult:
    """Verifica Digits/Dates(out) ⊆ Digits/Dates(in)"""
    pass

def validate_no_new_propn(original_doc, corrected_doc) -> ValidationResult:
    """Verifica que no aparezcan nuevos nombres propios"""
    pass

def validate_novelty_ratio(original_doc, corrected_doc, threshold=0.15) -> ValidationResult:
    """Verifica ratio de tokens nuevos ≤ 15%"""
    pass

def should_accept_correction(original_text, corrected_text, nlp) -> ValidationResult:
    """Orquesta todas las verificaciones"""
    pass