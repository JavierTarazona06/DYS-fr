"""
Test suite for Mistral LLM integration.
Validates model loading, correction quality, and guardrails.
"""
import sys
import subprocess
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import load_config
from src.guardrails.spacy_loader import load_french_nlp
from src.improvers.llm_improver import LLMImprover
from scripts.start_lt_server import start_lt_server_from_config


# Global variable to track server instance
_lt_server = None


def start_lt_server():
    """Start LanguageTool server using shared configuration."""
    global _lt_server
    
    print("Starting LanguageTool server...")
    cfg = load_config()
    server_url = f"http://{cfg['lt']['server']['host']}:{cfg['lt']['server']['port']}"
    
    _lt_server = start_lt_server_from_config()
    _lt_server.__enter__()
    
    # Wait for server to be ready
    for i in range(30):
        time.sleep(0.5)
        try:
            import requests
            response = requests.get(f"{server_url}/v2/languages", timeout=2)
            if response.status_code == 200:
                print(f"✓ Server started at {server_url}")
                return True
        except:
            continue
    
    return False


def stop_lt_server():
    """Stop LanguageTool server."""
    global _lt_server
    
    if _lt_server:
        print("\nStopping LanguageTool server...")
        _lt_server.__exit__(None, None, None)
        _lt_server = None


def test_mistral_model_exists():
    """Verify Mistral model file exists."""
    print("\n" + "="*70)
    print("TEST 1: Mistral Model File Check")
    print("="*70)
    
    cfg = load_config()
    model_name = cfg['llm']['model']
    base_name = model_name.replace('-7b-q4', '').replace('-q4', '')
    model_config = cfg['llm'][base_name]
    model_path = Path(cfg['llm']['models_dir']) / model_config['filename']
    
    if model_path.exists():
        size_gb = model_path.stat().st_size / 1e9
        print(f"✓ Model found: {model_path}")
        print(f"✓ Size: {size_gb:.2f} GB")
        return True
    else:
        print(f"✗ Model not found: {model_path}")
        print("\nDownload with: python scripts/download_mistral.py")
        return False


def test_mistral_loading():
    """Test Mistral model loads without errors."""
    print("\n" + "="*70)
    print("TEST 2: Mistral Model Loading")
    print("="*70)
    
    cfg = load_config()
    server_url = f"http://{cfg['lt']['server']['host']}:{cfg['lt']['server']['port']}"
    
    model_name = cfg['llm']['model']
    base_name = model_name.replace('-7b-q4', '').replace('-q4', '')
    model_config = cfg['llm'][base_name]
    model_path = Path(cfg['llm']['models_dir']) / model_config['filename']
    
    nlp = load_french_nlp(
        cfg['spacy']['model'],
        only_ner_pos=cfg['spacy']['only_ner_pos'],
        add_date_ruler=cfg['spacy']['add_date_ruler']
    )
    
    try:
        print("Loading model (this may take 10-30 seconds)...")
        improver = LLMImprover(
            model_path=str(model_path),
            lang='fr',
            lt_server_url=server_url,
            nlp=nlp,
            n_ctx=model_config['n_ctx'],
            max_tokens=model_config['max_tokens'],
            temperature=model_config['temperature'],
        )
        print(f"✓ Model loaded successfully")
        print(f"✓ Context size: {model_config['n_ctx']}")
        print(f"✓ Max tokens: {model_config['max_tokens']}")
        improver.close()
        return True
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        return False


def test_mistral_basic_correction():
    """Test Mistral corrections on simple errors."""
    print("\n" + "="*70)
    print("TEST 3: Basic Corrections")
    print("="*70)
    
    cfg = load_config()
    server_url = f"http://{cfg['lt']['server']['host']}:{cfg['lt']['server']['port']}"
    
    model_name = cfg['llm']['model']
    base_name = model_name.replace('-7b-q4', '').replace('-q4', '')
    model_config = cfg['llm'][base_name]
    model_path = Path(cfg['llm']['models_dir']) / model_config['filename']
    
    nlp = load_french_nlp(
        cfg['spacy']['model'],
        only_ner_pos=cfg['spacy']['only_ner_pos'],
        add_date_ruler=cfg['spacy']['add_date_ruler']
    )
    
    improver = LLMImprover(
        model_path=str(model_path),
        lang='fr',
        lt_server_url=server_url,
        nlp=nlp,
        n_ctx=model_config['n_ctx'],
        max_tokens=model_config['max_tokens'],
        temperature=model_config['temperature'],
    )
    
    # Test cases: (input, must_contain, must_not_contain)
    test_cases = [
        ("Je sui content.", "Je suis content.", "sui "),  # Conjugation
        ("Les chat mange.", "Le chat mange.", "Les chats mangent."),  # Plural 
        ("supermarchet", "supermarché", "supermarchet"),  # Typo
    ]
    
    passed = 0
    for input_text, must_have, must_not_have in test_cases:
        result = improver.improve(input_text, debug=False)
        
        has_correction = must_have.lower() in result.lower()
        no_error = must_not_have is None or must_not_have.lower() not in result.lower()
        
        if has_correction and no_error:
            print(f"✓ '{input_text}' → '{result}'")
            passed += 1
        else:
            print(f"✗ '{input_text}' → '{result}'")
            if not has_correction:
                print(f"  Missing: '{must_have}'")
            if not no_error:
                print(f"  Still contains: '{must_not_have}'")
    
    improver.close()
    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed >= len(test_cases) * 0.8  # 80% threshold


def test_mistral_entity_preservation(): #TODO: Check if mixing the response with the prompt ? It is not returning just the answer
    """Verify Mistral preserves entities."""
    print("\n" + "="*70)
    print("TEST 4: Entity Preservation")
    print("="*70)
    
    cfg = load_config()
    server_url = f"http://{cfg['lt']['server']['host']}:{cfg['lt']['server']['port']}"
    
    model_name = cfg['llm']['model']
    base_name = model_name.replace('-7b-q4', '').replace('-q4', '')
    model_config = cfg['llm'][base_name]
    model_path = Path(cfg['llm']['models_dir']) / model_config['filename']
    
    nlp = load_french_nlp(
        cfg['spacy']['model'],
        only_ner_pos=cfg['spacy']['only_ner_pos'],
        add_date_ruler=cfg['spacy']['add_date_ruler']
    )
    
    improver = LLMImprover(
        model_path=str(model_path),
        lang='fr',
        lt_server_url=server_url,
        nlp=nlp,
        n_ctx=model_config['n_ctx'],
        max_tokens=model_config['max_tokens'],
        temperature=model_config['temperature'],
    )
    
    test_cases = [
        ("Marie Dubois a acheter du pain.", "Marie Dubois"),
        ("Je vis a Paris depuis 2020.", "Paris"),
    ]
    
    passed = 0
    for input_text, entity in test_cases:
        result = improver.improve(input_text, debug=False)
        
        if entity in result:
            print(f"✓ Entity '{entity}' preserved")
            print(f"  '{input_text}' → '{result}'")
            passed += 1
        else:
            print(f"✗ Entity '{entity}' lost")
            print(f"  '{input_text}' → '{result}'")
    
    improver.close()
    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_mistral_no_hallucination(): #TODO: Check if mixing the response with the prompt ? It is not returning just the answer
    """Ensure Mistral doesn't add information."""
    print("\n" + "="*70)
    print("TEST 5: No Hallucination (Sense Preservation)")
    print("="*70)
    
    cfg = load_config()
    server_url = f"http://{cfg['lt']['server']['host']}:{cfg['lt']['server']['port']}"
    
    model_name = cfg['llm']['model']
    base_name = model_name.replace('-7b-q4', '').replace('-q4', '')
    model_config = cfg['llm'][base_name]
    model_path = Path(cfg['llm']['models_dir']) / model_config['filename']
    
    nlp = load_french_nlp(
        cfg['spacy']['model'],
        only_ner_pos=cfg['spacy']['only_ner_pos'],
        add_date_ruler=cfg['spacy']['add_date_ruler']
    )
    
    improver = LLMImprover(
        model_path=str(model_path),
        lang='fr',
        lt_server_url=server_url,
        nlp=nlp,
        n_ctx=model_config['n_ctx'],
        max_tokens=model_config['max_tokens'],
        temperature=model_config['temperature'],
    )
    
    # "aller" should stay "aller", not become "veux aller"
    test_text = "Je sui aller au magasin."
    result = improver.improve(test_text, debug=False)
    
    # Check that main verb (aller) is preserved in some form
    has_aller = "aller" in result.lower() or "allé" in result.lower()
    no_veux = "veux" not in result.lower()
    
    if has_aller and no_veux:
        print(f"✓ Sense preserved:")
        print(f"  '{test_text}' → '{result}'")
        improver.close()
        return True
    else:
        print(f"✗ Sense changed:")
        print(f"  '{test_text}' → '{result}'")
        improver.close()
        return False


def main():
    """Run all Mistral tests."""
    print("\n" + "="*70)
    print("MISTRAL LLM TEST SUITE")
    print("="*70)
    
    results = []
    server_started = False
    
    try:
        # Test 1: File exists
        results.append(("Model File Check", test_mistral_model_exists()))
        
        if not results[0][1]:
            print("\n⚠️  Model not downloaded. Download with:")
            print("python scripts/download_mistral.py")
            return 1
        
        # Test 2: Loading
        results.append(("Model Loading", test_mistral_loading()))
        
        if not results[1][1]:
            print("\n⚠️  Failed to load model. Check llama-cpp-python installation:")
            print("pip install llama-cpp-python --prefer-binary")
            return 1
        
        # Start LT server for correction tests
        if not start_lt_server():
            print("\n⚠️  Failed to start LanguageTool server")
            print("Skipping correction tests.")
            return 1
        server_started = True
        
        # Test 3-5: Functionality
        results.append(("Basic Corrections", test_mistral_basic_correction()))
        results.append(("Entity Preservation", test_mistral_entity_preservation()))
        results.append(("No Hallucination", test_mistral_no_hallucination()))
        
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
    
    finally:
        if server_started:
            stop_lt_server()


if __name__ == "__main__":
    sys.exit(main())
