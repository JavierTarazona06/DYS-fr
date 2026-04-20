"""
Test suite for LanguageTool integration.
Validates LT server connectivity, correction quality, and filtering logic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import load_config
from src.improvers.lt_improver import LTImprover
from src.guardrails.spacy_loader import load_french_nlp


def test_lt_server_connectivity(lt_server):
    """Test LanguageTool server is accessible."""
    print("\n" + "="*70)
    print("TEST 1: Server Connectivity")
    print("="*70)
    
    server_url = lt_server
    cfg = load_config()
    
    try:
        import requests
        response = requests.get(f"{server_url}/v2/languages", timeout=5)
        assert response.status_code == 200, f"Server returned {response.status_code}"
        print(f"✓ Server accessible at {server_url}")
        print(f"✓ Available languages: {len(response.json())} detected")
    except Exception as e:
        pytest.fail(f"Server connection failed: {e}")


def test_lt_basic_correction(lt_server):
    """Test basic LanguageTool corrections."""
    print("\n" + "="*70)
    print("TEST 2: Basic Corrections")
    print("="*70)
    
    server_url = lt_server
    cfg = load_config()
    
    # Load spaCy for NER
    nlp = load_french_nlp(
        cfg['spacy']['model'],
        only_ner_pos=cfg['spacy']['only_ner_pos'],
        add_date_ruler=cfg['spacy']['add_date_ruler']
    )
    
    improver = LTImprover(lang='fr', server_url=server_url, nlp=nlp)
    
    # Test cases: (input, expected_correction_contains)
    test_cases = [
        ("Je sui content.", "suis"),  # Conjugation
        ("Les chiens aboie.", "aboient"),  # Plural verb agreement (clear plural context)
        ("Il a manger.", "mangé"),  # Participle
        ("Cest bon.", "C'est"),  # Apostrophe
    ]
    
    passed = 0
    for input_text, expected in test_cases:
        result = improver.improve(input_text)
        if expected.lower() in result.lower():
            print(f"✓ '{input_text}' → '{result}'")
            passed += 1
        else:
            print(f"✗ '{input_text}' → '{result}' (expected '{expected}')")
    
    assert passed == len(test_cases), f"Only {passed}/{len(test_cases)} tests passed"


def test_lt_entity_preservation(lt_server):
    """Verify entities (names, dates, numbers) are preserved."""
    print("\n" + "="*70)
    print("TEST 3: Entity Preservation")
    print("="*70)
    
    cfg = load_config()
    server_url = lt_server
    nlp = load_french_nlp(cfg['spacy']['model'])
    
    improver = LTImprover(lang='fr', server_url=server_url, nlp=nlp)
    
    # Test cases with entities that should NOT change
    test_cases = [
        ("Marie Dubois a acheter du pain.", "Marie Dubois"),  # Name
        ("Le 14 juillet est une fete.", "14 juillet"),  # Date
        ("J'ai 25 euro.", "25"),  # Number
    ]
    
    passed = 0
    for input_text, entity in test_cases:
        result = improver.improve(input_text)
        if entity in result:
            print(f"✓ Entity '{entity}' preserved: {result}")
            passed += 1
        else:
            print(f"✗ Entity '{entity}' lost in: {result}")
    
    assert passed == len(test_cases), f"Only {passed}/{len(test_cases)} tests passed"


def test_lt_no_info_addition(lt_server):
    """Ensure LT doesn't add information to incomplete text."""
    print("\n" + "="*70)
    print("TEST 4: No Information Addition (Anti-Cheating)")
    print("="*70)
    
    cfg = load_config()
    server_url = lt_server
    nlp = load_french_nlp(cfg['spacy']['model'])
    
    improver = LTImprover(lang='fr', server_url=server_url, nlp=nlp)
    
    # Incomplete texts that should remain incomplete
    test_cases = [
        "La capitale de France est ..",
        "L'année de l'indépendance des États-Unis est ..",
        "Le président actuel de la France est ..",
    ]
    
    passed = 0
    for input_text in test_cases:
        result = improver.improve(input_text)
        # Check that ".." remains (or similar placeholder)
        if ".." in result or "..." in result or result == input_text or result==input_text[:-3]+'.':
            print(f"✓ Incomplete text preserved: '{result}'")
            passed += 1
        else:
            print(f"✗ Information added: '{result}'")
    
    assert passed == len(test_cases), f"Only {passed}/{len(test_cases)} tests passed"
