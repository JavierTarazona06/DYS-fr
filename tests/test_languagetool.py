"""
Test suite for LanguageTool integration.
Validates LT server connectivity, correction quality, and filtering logic.
"""
import sys
import subprocess
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import load_config
from src.improvers.lt_improver import LTImprover
from src.guardrails.spacy_loader import load_french_nlp


# Global variable to track server process
_server_process = None


def start_lt_server():
    """Start LanguageTool server using runner.py."""
    global _server_process
    
    print("Starting LanguageTool server...")
    project_root = Path(__file__).parent.parent
    server_script = project_root / "scripts" / "start_lt_server.py"
    
    _server_process = subprocess.Popen(
        [sys.executable, str(server_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(project_root)
    )
    
    # Wait for server to start (check every 0.5s for up to 15s)
    cfg = load_config()
    server_url = f"http://{cfg['lt']['server']['host']}:{cfg['lt']['server']['port']}"
    
    for i in range(30):
        time.sleep(0.5)
        try:
            import requests
            response = requests.get(f"{server_url}/v2/languages", timeout=2)
            if response.status_code == 200:
                print(f"✓ Server started successfully at {server_url}")
                return True
        except:
            continue
    
    print("✗ Server failed to start within 15 seconds")
    return False


def stop_lt_server():
    """Stop LanguageTool server."""
    global _server_process
    
    if _server_process:
        print("\nStopping LanguageTool server...")
        _server_process.terminate()
        try:
            _server_process.wait(timeout=5)
            print("✓ Server stopped")
        except subprocess.TimeoutExpired:
            _server_process.kill()
            print("✓ Server forcefully stopped")
        _server_process = None


def test_lt_server_connectivity():
    """Verify LanguageTool server is accessible."""
    print("\n" + "="*70)
    print("TEST 1: LanguageTool Server Connectivity")
    print("="*70)
    
    cfg = load_config()
    server_url = f"http://{cfg['lt']['server']['host']}:{cfg['lt']['server']['port']}"
    
    try:
        import requests
        response = requests.get(f"{server_url}/v2/languages", timeout=5)
        assert response.status_code == 200, f"Server returned {response.status_code}"
        print(f"✓ Server accessible at {server_url}")
        print(f"✓ Available languages: {len(response.json())} detected")
        return True
    except Exception as e:
        print(f"✗ Server connection failed: {e}")
        print("\nStart server with: python runner.py")
        return False


def test_lt_basic_correction():
    """Test basic LanguageTool corrections."""
    print("\n" + "="*70)
    print("TEST 2: Basic LanguageTool Corrections")
    print("="*70)
    
    cfg = load_config()
    server_url = f"http://{cfg['lt']['server']['host']}:{cfg['lt']['server']['port']}"
    
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
    
    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_lt_entity_preservation():
    """Verify entities (names, dates, numbers) are preserved."""
    print("\n" + "="*70)
    print("TEST 3: Entity Preservation")
    print("="*70)
    
    cfg = load_config()
    server_url = f"http://{cfg['lt']['server']['host']}:{cfg['lt']['server']['port']}"
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
    
    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_lt_no_info_addition():
    """Ensure LT doesn't add information to incomplete text."""
    print("\n" + "="*70)
    print("TEST 4: No Information Addition (Anti-Cheating)")
    print("="*70)
    
    cfg = load_config()
    server_url = f"http://{cfg['lt']['server']['host']}:{cfg['lt']['server']['port']}"
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
    
    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def main():
    """Run all LanguageTool tests."""
    print("\n" + "="*70)
    print("LANGUAGETOOL TEST SUITE")
    print("="*70)
    
    results = []
    server_started = False
    
    try:
        # Start server
        if not start_lt_server():
            print("\n⚠️  Failed to start server. Check runner.py")
            return 1
        server_started = True
        
        # Test 1: Connectivity
        results.append(("Server Connectivity", test_lt_server_connectivity()))
        
        if not results[0][1]:
            print("\n⚠️  Server connectivity failed")
            print("Skipping remaining tests.")
            return 1
        
        # Test 2-4: Functionality
        results.append(("Basic Corrections", test_lt_basic_correction()))
        results.append(("Entity Preservation", test_lt_entity_preservation()))
        results.append(("No Info Addition", test_lt_no_info_addition()))
        
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
        # Always stop server
        if server_started:
            stop_lt_server()


if __name__ == "__main__":
    sys.exit(main())
