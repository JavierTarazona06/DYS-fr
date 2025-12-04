"""
Test suite for Mistral LLM integration (pytest version).
Keeps prints for visibility.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import load_config
from src.guardrails.spacy_loader import load_french_nlp
from src.improvers.llm_improver import LLMImprover

@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture(scope="session")
def model_cfg(cfg):
    model_name = cfg["llm"]["model"]
    base_name = model_name.replace("-7b-q4", "").replace("-q4", "")
    return cfg["llm"][base_name]


@pytest.fixture(scope="session")
def model_path(cfg, model_cfg):
    return Path(cfg["llm"]["models_dir"]) / model_cfg["filename"]


@pytest.fixture(scope="session")
def nlp(cfg):
    return load_french_nlp(
        cfg["spacy"]["model"],
        only_ner_pos=cfg["spacy"]["only_ner_pos"],
        add_date_ruler=cfg["spacy"]["add_date_ruler"],
    )


def test_mistral_model_exists(model_path):
    """Verify Mistral model file exists."""
    print("\n" + "=" * 70)
    print("TEST 1: Mistral Model File Check")
    print("=" * 70)

    if not model_path.exists():
        print(f"✗ Model not found: {model_path}")
        print("\nDownload with: python scripts/download_mistral.py")
        pytest.fail(f"Model missing: {model_path}")

    size_gb = model_path.stat().st_size / 1e9
    print(f"✓ Model found: {model_path}")
    print(f"✓ Size: {size_gb:.2f} GB")


def test_mistral_loading(model_path, model_cfg, nlp, lt_server):
    """Test Mistral model loads without errors."""
    print("\n" + "=" * 70)
    print("TEST 2: Mistral Model Loading")
    print("=" * 70)

    try:
        print("Loading model (this may take 10-30 seconds)...")
        improver = LLMImprover(
            model_path=str(model_path),
            lang="fr",
            lt_server_url=lt_server,
            nlp=nlp,
            n_ctx=model_cfg["n_ctx"],
            max_tokens=model_cfg["max_tokens"],
            temperature=model_cfg["temperature"],
        )
        print("✓ Model loaded successfully")
        print(f"✓ Context size: {model_cfg['n_ctx']}")
        print(f"✓ Max tokens: {model_cfg['max_tokens']}")
    finally:
        try:
            improver.close()
        except Exception:
            pass


def test_mistral_basic_correction(model_path, model_cfg, nlp, lt_server):
    """Test Mistral corrections on simple errors."""
    print("\n" + "=" * 70)
    print("TEST 3: Basic Corrections")
    print("=" * 70)

    improver = LLMImprover(
        model_path=str(model_path),
        lang="fr",
        lt_server_url=lt_server,
        nlp=nlp,
        n_ctx=model_cfg["n_ctx"],
        max_tokens=model_cfg["max_tokens"],
        temperature=model_cfg["temperature"],
    )

    test_cases = [
        ("Je sui content.", "Je suis content.", "sui "),
        ("Les chat mange.", "Le chat mange.", "Les chats mangent."),
        ("supermarchet", "supermarché", "supermarchet"),
    ]

    passed = 0
    for input_text, must_have, must_not_have in test_cases:
        result = improver.improve(input_text, debug=False)

        has_correction = must_have.lower() in result.lower()
        no_error = must_not_have is None or must_not_have.lower() not in result.lower()

        status = "OK" if has_correction and no_error else "FAIL"
        print(f"[{status}] '{input_text}' → '{result}'")
        if not has_correction:
            print(f"  Missing: '{must_have}'")
        if not no_error:
            print(f"  Still contains: '{must_not_have}'")

        if has_correction and no_error:
            passed += 1

    try:
        improver.close()
    finally:
        pass

    assert passed >= len(test_cases) * 0.8, f"Passed {passed}/{len(test_cases)}"


def test_mistral_entity_preservation(model_path, model_cfg, nlp, lt_server):
    """Verify Mistral preserves entities."""
    print("\n" + "=" * 70)
    print("TEST 4: Entity Preservation")
    print("=" * 70)

    improver = LLMImprover(
        model_path=str(model_path),
        lang="fr",
        lt_server_url=lt_server,
        nlp=nlp,
        n_ctx=model_cfg["n_ctx"],
        max_tokens=model_cfg["max_tokens"],
        temperature=model_cfg["temperature"],
    )

    test_cases = [
        ("Marie Dubois a acheter du pain.", ["Marie Dubois"]),
        #("Je vis a Paris depuis 2020.", ["Paris", "2020"]),
    ]

    passed = 0
    for input_text, entities in test_cases:
        result = improver.improve(input_text, debug=True)
        all_preserved = all(entity in result for entity in entities)

        status = "OK" if all_preserved else "FAIL"
        print(f"[{status}] '{input_text}' → '{result}'")
        if not all_preserved:
            missing = [e for e in entities if e not in result]
            print(f"  Missing: {missing}")
        if all_preserved:
            passed += 1

    try:
        improver.close()
    finally:
        pass

    assert passed == len(test_cases), f"Passed {passed}/{len(test_cases)}"


def test_mistral_no_hallucination(model_path, model_cfg, nlp, lt_server):
    """Ensure Mistral doesn't add information."""
    print("\n" + "=" * 70)
    print("TEST 5: No Hallucination (Sense Preservation)")
    print("=" * 70)

    improver = LLMImprover(
        model_path=str(model_path),
        lang="fr",
        lt_server_url=lt_server,
        nlp=nlp,
        n_ctx=model_cfg["n_ctx"],
        max_tokens=model_cfg["max_tokens"],
        temperature=model_cfg["temperature"],
    )

    test_text = "Je sui aller au magasin."
    result = improver.improve(test_text, debug=False)

    has_aller = "aller" in result.lower() or "allé" in result.lower()
    no_veux = "veux" not in result.lower()

    status = "OK" if has_aller and no_veux else "FAIL"
    print(f"[{status}] '{test_text}' → '{result}'")
    if not has_aller:
        print("  Missing: aller/allé")
    if not no_veux:
        print("  Contains: 'veux'")

    try:
        improver.close()
    finally:
        pass

    assert has_aller and no_veux, "Sense not preserved"


def test_mistral_dyslexic_paragraph(model_path, model_cfg, nlp, lt_server):
    """Test Mistral with a realistic dyslexic text paragraph."""
    print("\n" + "=" * 70)
    print("TEST 6: Dyslexic Paragraph Correction")
    print("=" * 70)

    improver = LLMImprover(
        model_path=str(model_path),
        lang="fr",
        lt_server_url=lt_server,
        nlp=nlp,
        n_ctx=model_cfg["n_ctx"],
        max_tokens=model_cfg["max_tokens"],
        temperature=model_cfg["temperature"],
    )

    test_text = (
        "Aujourdhui je sui alé a l ecol avec mon copin Toma. "
        "On a prandue un cour de fransé mé jarrive pa bien a ecrir les mot, "
        "je confon toujour les letre et les accent. "
        "La proffeseur a di que c pa grav, que je peu recomancé et prand mon temp, "
        "mé sa me stresse kan mé camarade finisse plu vit. "
        "Apres le cour on a fait du spore dans la cour et sa me rendai plus hereu "
        "car je panse pa tro au devair a faire se soir."
    )

    print("\n📝 INPUT:")
    print("-" * 70)
    print(test_text)
    print("-" * 70)

    result = improver.improve(test_text, debug=False)

    print("\n✅ OUTPUT:")
    print("-" * 70)
    print(result)
    print("-" * 70)

    # Verify some corrections were made
    has_corrections = (
        result != test_text and
        len(result) > 0 and
        "Toma" in result  # Entity preservation
    )

    print("\n🔍 VALIDATION:")
    
    if has_corrections:
        print("  ✓ Text was improved")
    else:
        print("  ✗ No improvements detected")

    try:
        improver.close()
    finally:
        pass

    assert has_corrections, "Dyslexic text not properly corrected"
