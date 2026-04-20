#!/usr/bin/env python3
"""
Test Mistral-7B-Instruct v0.3 model locally.
Verifies that the model loads and generates text correctly.
"""

import sys
from pathlib import Path

# Check if llama-cpp-python is installed
try:
    from llama_cpp import Llama
except ImportError:
    print("✗ Error: llama-cpp-python is not installed")
    print("\nInstall it with:")
    print("  pip install llama-cpp-python --prefer-binary")
    sys.exit(1)


def main():
    # Locate model
    script_dir = Path(__file__).parent.parent
    models_dir = script_dir / "resources" / "models"
    model_path = models_dir / "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
    
    # Check if model exists
    if not model_path.exists():
        print(f"✗ Error: Model not found at {model_path}")
        print("\nDownload it with:")
        print("  python scripts/download_mistral.py")
        sys.exit(1)
    
    print(f"{'='*60}")
    print("Testing Mistral-7B-Instruct v0.3 Q4_K_M")
    print(f"{'='*60}")
    print(f"Model: {model_path.name}")
    print(f"Size: {model_path.stat().st_size / (1024**3):.2f} GB")
    print(f"{'='*60}\n")
    
    # Load model
    print("Loading model (this may take a moment)...")
    try:
        llm = Llama(
            model_path=str(model_path),
            n_ctx=2048,          # Context window (smaller = less RAM)
            n_threads=4,         # CPU threads
            n_gpu_layers=0,      # CPU only
            use_mlock=False,     # Don't lock model in RAM (safer for low RAM)
            use_mmap=True,       # Use memory mapping
            verbose=False,
        )
        print("✓ Model loaded successfully!\n")
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        sys.exit(1)
    
    # Test prompt (French grammar correction)
    prompt = """<s>[INST] Tu es un assistant qui corrige le texte français SANS AJOUTER d'informations nouvelles.

Règles strictes:
1. Ne change JAMAIS les nombres, dates ou noms propres
2. N'ajoute AUCUNE information manquante
3. Corrige uniquement la grammaire, orthographe et ponctuation

Texte à corriger:
"Je mange un pomme à Paris. C'est très bon."

Texte corrigé: [/INST]"""
    
    print("Test prompt (French grammar correction):")
    print("-" * 60)
    print(prompt)
    print("-" * 60)
    print("\nGenerating response...\n")
    
    # Generate
    try:
        response = llm(
            prompt,
            max_tokens=100,
            temperature=0.3,
            stop=["</s>", "[INST]"],
            echo=False,
        )
        
        output = response['choices'][0]['text'].strip()
        
        print("Response:")
        print("=" * 60)
        print(output)
        print("=" * 60)
        
        # Show statistics
        stats = response.get('usage', {})
        if stats:
            print(f"\nStatistics:")
            print(f"  Prompt tokens: {stats.get('prompt_tokens', 'N/A')}")
            print(f"  Generated tokens: {stats.get('completion_tokens', 'N/A')}")
            print(f"  Total tokens: {stats.get('total_tokens', 'N/A')}")
        
        print(f"\n✓ Test completed successfully!")
        
    except KeyboardInterrupt:
        print("\n\n✗ Generation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Generation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("\n")
    main()
    print("\n" + "="*60)
