#!/usr/bin/env python3
"""
Download smaller Mistral model for faster testing.
Q4_K_S is ~2.4 GB vs Q4_K_M ~4.4 GB
"""

import sys
import subprocess
from pathlib import Path

def main():
    # Smaller model - Q4_K_S (~2.4 GB vs ~4.4 GB)
    REPO_ID = "bartowski/Mistral-7B-Instruct-v0.3-GGUF"
    FILENAME = "Mistral-7B-Instruct-v0.3-Q4_K_S.gguf"  # Smaller version
    
    # Local directory
    script_dir = Path(__file__).parent.parent
    models_dir = script_dir / "resources" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"Downloading SMALLER Mistral model for testing")
    print(f"{'='*60}")
    print(f"Model: Q4_K_S (smaller, faster to download)")
    print(f"Size: ~2.4 GB (vs ~4.4 GB for Q4_K_M)")
    print(f"Quality: Slightly lower but still good for testing")
    print(f"{'='*60}\n")
    
    # Install huggingface_hub if needed
    try:
        import huggingface_hub
    except ImportError:
        print("Installing huggingface_hub...")
        subprocess.run([sys.executable, "-m", "pip", "install", "huggingface_hub"], check=True)
    
    from huggingface_hub import hf_hub_download
    
    try:
        file_path = hf_hub_download(
            repo_id=REPO_ID,
            filename=FILENAME,
            local_dir=str(models_dir),
            local_dir_use_symlinks=False,
            resume_download=True  # Can resume if interrupted
        )
        
        file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
        print(f"\n✓ Download complete!")
        print(f"  Location: {file_path}")
        print(f"  Size: {file_size_mb:.1f} MB")
        return file_path
        
    except Exception as e:
        print(f"✗ Error: {e}")
        print("\nManual download:")
        print(f"huggingface-cli download {REPO_ID} {FILENAME} --local-dir {models_dir} --resume-download")
        sys.exit(1)

if __name__ == "__main__":
    main()
