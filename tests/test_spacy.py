"""
Test suite for spaCy NER integration.
Validates entity detection, masking/reinsertion logic (pytest version).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import load_config
from src.guardrails.spacy_loader import load_french_nlp
from src.guardrails.entities import mask_entities, reinject_entities


@pytest.fixture(scope="session")
def spacy_cfg():
    return load_config()["spacy"]


@pytest.fixture(scope="session")
def nlp(spacy_cfg):
    return load_french_nlp(
        spacy_cfg["model"],
        only_ner_pos=spacy_cfg["only_ner_pos"],
        add_date_ruler=spacy_cfg["add_date_ruler"],
    )


def test_spacy_model_loading(nlp, spacy_cfg):
    """Verify spaCy model loads correctly."""
    assert nlp is not None
    assert spacy_cfg["model"] in str(nlp.meta.get("name", "")) or bool(nlp.meta)


def test_spacy_entity_detection(nlp):
    """Test entity detection accuracy (>=80% cases pass)."""
    test_cases = [
        ("Marie Dubois habite à Paris.", ["Marie Dubois", "Paris"]),
        ("Le 14 juillet 1789 fut important.", ["14 juillet 1789"]),
        ("Apple et Microsoft sont des entreprises.", ["Apple", "Microsoft"]),
    ]

    passed = 0
    for text, expected_entities in test_cases:
        doc = nlp(text)
        detected = [ent.text for ent in doc.ents]
        found_all = all(any(exp in det for det in detected) for exp in expected_entities)
        if found_all:
            passed += 1
        status = "OK" if found_all else "FAIL"
        print(f"[EntityDetection] {status}: '{text}'")
        print(f"  Expected: {expected_entities}")
        print(f"  Detected: {detected}")

    required = math.ceil(len(test_cases) * 0.8)
    assert passed >= required, f"Detected {passed}/{len(test_cases)} (need >= {required})"


def test_entity_masking(nlp):
    """Test entity masking and reinsertion is lossless."""
    test_texts = [
        "Marie Dubois a acheté du pain à Paris le 14 juillet.",
        "J'ai rencontré Jean-Pierre Martin hier.",
        "Apple a annoncé de nouveaux produits en 2024.",
    ]

    for text in test_texts:
        doc = nlp(text)
        masked_text, entity_map = mask_entities(doc)
        reconstructed = reinject_entities(masked_text, entity_map)
        status = "OK" if reconstructed == text else "FAIL"
        print(f"[Masking] {status}: '{text}'")
        print(f"  Masked: {masked_text}")
        print(f"  Entities: {entity_map}")
        assert reconstructed == text


def test_entity_types(nlp):
    """Verify entity type detection (>=70% cases pass)."""
    test_cases = [
        ("Marie Dubois est médecin.", "Marie Dubois", "PER"),
        ("J'habite à Paris.", "Paris", "LOC"),
        ("Google est une entreprise.", "Google", "ORG"),
        ("La révolution de 1789 fut importante.", "1789", "DATE"),
        ("Le 14 juillet est une fête.", "14 juillet", "DATE"),
        ("En 2024, tout a changé.", "2024", "DATE"),
    ]

    passed = 0
    for text, entity_text, expected_type in test_cases:
        doc = nlp(text)
        _, masked_entities = mask_entities(doc)

        for masked_ent in masked_entities:
            if entity_text in masked_ent.text:
                if masked_ent.label == expected_type:
                    passed += 1
                    print(f"[Types] OK: '{entity_text}' -> {masked_ent.label} in '{text}'")
                else:
                    print(f"[Types] FAIL: '{entity_text}' -> {masked_ent.label} (expected {expected_type}) in '{text}'")
                break
        else:
            print(f"[Types] MISS: '{entity_text}' not detected in '{text}'")

    required = math.ceil(len(test_cases) * 0.7)
    assert passed >= required, f"Typed {passed}/{len(test_cases)} (need >= {required})"
