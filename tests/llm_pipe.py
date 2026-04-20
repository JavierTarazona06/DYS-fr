"""
Test del pipeline completo de LLMImprover en modo debug.
"""
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import load_config
from src.guardrails.spacy_loader import load_french_nlp
from src.improvers.llm_improver import LLMImprover


def main():
    # Load configuration
    cfg = load_config()
    
    # Build paths
    model_name = cfg['llm']['model']
    base_name = model_name.replace('-7b-q4', '').replace('-q4', '')
    model_config = cfg['llm'][base_name]
    model_path = Path(cfg['llm']['models_dir']) / model_config['filename']
    
    if not model_path.exists():
        print(f"❌ Error: Model not found at {model_path}")
        print("\nPlease run: python scripts/download_mistral.py")
        return 1
    
    print(f"✓ Model found: {model_path}")
    print(f"✓ Loading spaCy model: {cfg['spacy']['model']}")
    
    # Load spaCy
    nlp = load_french_nlp(
        cfg['spacy']['model'],
        only_ner_pos=cfg['spacy']['only_ner_pos'],
        add_date_ruler=cfg['spacy']['add_date_ruler'],
    )
    
    print(f"✓ Loading LLM (this may take 10-30 seconds)...")
    
    # Initialize LLMImprover
    improver = LLMImprover(
        model_path=str(model_path),
        lang=cfg['lt']['lang'],
        lt_server_url=f"http://{cfg['lt']['server']['host']}:{cfg['lt']['server']['port']}",
        nlp=nlp,
        n_ctx=model_config['n_ctx'],
        max_tokens=model_config['max_tokens'],
        temperature=model_config['temperature'],
    )
    
    print(f"✓ LLM loaded successfully!\n")
    
    # Test text
    test_text = "Je sui aller a lécol se matin mes jé oublier mon livr. La prof ma di que cétai pa trés grave mé je devré fer plus atention. Apré la cour jai voulu parlé a mon ami mé il mavé pa vu, sa ma fé un peu mal."
    
    print(f"{'='*70}")
    print("TEST: Pipeline LLMImprover avec debug activé")
    print(f"{'='*70}\n")
    
    # Run with debug mode
    result = improver.improve(test_text, debug=True)
    
    print(f"\n{'='*70}")
    print("COMPARAISON FINALE")
    print(f"{'='*70}")
    print(f"\nAVANT:\n{test_text}")
    print(f"\nAPRÈS:\n{result}")
    print(f"\n{'='*70}\n")
    
    # Cleanup
    improver.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
