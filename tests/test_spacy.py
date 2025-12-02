"""
Test suite for spaCy NER integration.
Validates entity detection, masking/reinsertion logic.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import load_config
from src.guardrails.spacy_loader import load_french_nlp
from src.guardrails.entities import mask_entities, reinject_entities


def test_spacy_model_loading():
    """Verify spaCy model loads correctly."""
    print("\n" + "="*70)
    print("TEST 1: spaCy Model Loading")
    print("="*70)
    
    cfg = load_config()
    
    try:
        nlp = load_french_nlp(
            cfg['spacy']['model'],
            only_ner_pos=cfg['spacy']['only_ner_pos'],
            add_date_ruler=cfg['spacy']['add_date_ruler']
        )
        print(f"✓ Model '{cfg['spacy']['model']}' loaded")
        print(f"✓ Pipeline components: {nlp.pipe_names}")
        return True
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        print("\nInstall with: python -m spacy download fr_core_news_md")
        return False


def test_spacy_entity_detection():
    """Test entity detection accuracy."""
    print("\n" + "="*70)
    print("TEST 2: Entity Detection")
    print("="*70)
    
    cfg = load_config()
    nlp = load_french_nlp(
        cfg['spacy']['model'],
        only_ner_pos=cfg['spacy']['only_ner_pos'],
        add_date_ruler=cfg['spacy']['add_date_ruler']
    )
    
    # Test cases: (text, expected_entities)
    test_cases = [
        ("Marie Dubois habite à Paris.", ["Marie Dubois", "Paris"]),
        ("Le 14 juillet 1789 fut important.", ["14 juillet 1789"]),
        ("Apple et Microsoft sont des entreprises.", ["Apple", "Microsoft"]),
    ]
    
    passed = 0
    for text, expected_entities in test_cases:
        doc = nlp(text)
        detected = [ent.text for ent in doc.ents]
        
        # Check if all expected entities are detected
        found_all = all(any(exp in det for det in detected) for exp in expected_entities)
        
        if found_all:
            print(f"✓ '{text}'")
            print(f"  Detected: {detected}")
            passed += 1
        else:
            print(f"✗ '{text}'")
            print(f"  Expected: {expected_entities}")
            print(f"  Detected: {detected}")
    
    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed >= len(test_cases) * 0.8  # 80% threshold


def test_entity_masking():
    """Test entity masking and reinsertion."""
    print("\n" + "="*70)
    print("TEST 3: Entity Masking & Reinsertion")
    print("="*70)
    
    cfg = load_config()
    nlp = load_french_nlp(
        cfg['spacy']['model'],
        only_ner_pos=cfg['spacy']['only_ner_pos'],
        add_date_ruler=cfg['spacy']['add_date_ruler']
    )
    
    test_texts = [
        "Marie Dubois a acheté du pain à Paris le 14 juillet.",
        "J'ai rencontré Jean-Pierre Martin hier.",
        "Apple a annoncé de nouveaux produits en 2024.",
    ]
    
    passed = 0
    for text in test_texts:
        doc = nlp(text)
        
        # Mask entities
        masked_text, entity_map = mask_entities(doc)
        
        # Reinject entities
        reconstructed = reinject_entities(masked_text, entity_map)
        
        if reconstructed == text:
            print(f"✓ Original: {text}")
            print(f"  Masked:   {masked_text}")
            print(f"  Restored: {reconstructed}")
            passed += 1
        else:
            print(f"✗ Original: {text}")
            print(f"  Restored: {reconstructed}")
            print(f"  Entities: {entity_map}")
    
    print(f"\nPassed: {passed}/{len(test_texts)}")
    return passed == len(test_texts)


def test_entity_types():
    """Verify correct entity type detection."""
    print("\n" + "="*70)
    print("TEST 4: Entity Type Classification")
    print("="*70)
    
    cfg = load_config()
    nlp = load_french_nlp(
        cfg['spacy']['model'],
        only_ner_pos=cfg['spacy']['only_ner_pos'],
        add_date_ruler=cfg['spacy']['add_date_ruler']
    )
    
    # Test cases: (text, entity, expected_type)
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
        
        # Use mask_entities to get all detected entities (spaCy + regex)
        _, masked_entities = mask_entities(doc)
        
        found = False
        for masked_ent in masked_entities:
            if entity_text in masked_ent.text:
                if masked_ent.label == expected_type:
                    print(f"✓ '{entity_text}' → {masked_ent.label}")
                    passed += 1
                    found = True
                else:
                    print(f"✗ '{entity_text}' → {masked_ent.label} (expected {expected_type})")
                    found = True
                break
        
        if not found:
            print(f"✗ '{entity_text}' not detected in '{text}'")
    
    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed >= len(test_cases) * 0.7  # 70% threshold (spaCy not perfect)


def main():
    """Run all spaCy tests."""
    print("\n" + "="*70)
    print("SPACY NER TEST SUITE")
    print("="*70)
    
    results = []
    
    # Test 1: Loading
    results.append(("Model Loading", test_spacy_model_loading()))
    
    if not results[0][1]:
        print("\n⚠️  Model not installed. Install with:")
        print("python -m spacy download fr_core_news_md")
        return 1
    
    # Test 2-4: Functionality
    results.append(("Entity Detection", test_spacy_entity_detection()))
    results.append(("Masking/Reinsertion", test_entity_masking()))
    results.append(("Entity Types", test_entity_types()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    total_passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {total_passed}/{len(results)} passed")
    print("="*70 + "\n")
    
    return 0 if total_passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
