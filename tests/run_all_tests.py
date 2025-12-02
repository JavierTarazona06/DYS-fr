"""
Master test runner for DYS-fr project.
Runs all component tests in sequence and provides summary.
"""
import sys
import subprocess
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_test_suite(name, script):
    """Run a test suite and return (name, passed)."""
    print(f"\n{'#'*70}")
    print(f"# Running: {name}")
    print(f"{'#'*70}\n")
    
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=False,
            text=True,
            check=False
        )
        return (name, result.returncode == 0)
    except Exception as e:
        print(f"\n✗ Failed to run {name}: {e}")
        return (name, False)


def main():
    """Run all test suites."""
    print("\n" + "="*70)
    print("DYS-FR COMPREHENSIVE TEST SUITE")
    print("="*70)
    print("\nThis will test:")
    print("  1. LanguageTool (server, corrections, guardrails)")
    print("  2. spaCy (NER, entity masking/reinsertion)")
    print("  3. Mistral LLM (loading, corrections, safety)")
    print("\nPrerequisites:")
    print("  - LanguageTool server running (python runner.py)")
    print("  - spaCy model installed (python -m spacy download fr_core_news_md)")
    print("  - Mistral model downloaded (python scripts/download_mistral.py)")
    print("="*70)
    
    input("\nPress Enter to continue or Ctrl+C to cancel...")
    
    tests_dir = Path(__file__).parent
    
    # Define test suites in order
    test_suites = [
        ("LanguageTool", tests_dir / "test_languagetool.py"),
        ("spaCy NER", tests_dir / "test_spacy.py"),
        ("Mistral LLM", tests_dir / "test_llm_mistral.py"),
    ]
    
    results = []
    for name, script in test_suites:
        if script.exists():
            results.append(run_test_suite(name, script))
        else:
            print(f"\n⚠️  Warning: {script} not found, skipping.")
            results.append((name, False))
    
    # Final summary
    print("\n" + "="*70)
    print("OVERALL TEST SUMMARY")
    print("="*70)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    total_passed = sum(1 for _, p in results if p)
    total_tests = len(results)
    
    print(f"\nTotal: {total_passed}/{total_tests} suites passed")
    
    if total_passed == total_tests:
        print("\n🎉 All tests passed! System is ready for production.")
    else:
        print(f"\n⚠️  {total_tests - total_passed} suite(s) failed. Review logs above.")
    
    print("="*70 + "\n")
    
    return 0 if total_passed == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())
