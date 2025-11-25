#!/usr/bin/env python3
"""
Alternative download script for Mistral-7B-Instruct v0.3 Q4_K_M.
Uses bartowski's repository which is more reliable.
"""

import sys
import subprocess
from pathlib import Path
from urllib.request import urlretrieve, Request, urlopen
from urllib.error import URLError, HTTPError


def download_with_progress(url: str, destination: Path):
    """Download file with progress bar."""
    
    def report_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(100, downloaded * 100 / total_size)
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            
            bar_length = 50
            filled = int(bar_length * percent / 100)
            bar = '█' * filled + '░' * (bar_length - filled)
            
            print(f'\r[{bar}] {percent:.1f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB)', end='', flush=True)
    
    print(f"Downloading to: {destination}")
    
    # Add headers to avoid 403 errors
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urlopen(req) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            
            with open(destination, 'wb') as out_file:
                block_size = 8192
                downloaded = 0
                
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    
                    out_file.write(buffer)
                    downloaded += len(buffer)
                    
                    if total_size > 0:
                        percent = min(100, downloaded * 100 / total_size)
                        downloaded_mb = downloaded / (1024 * 1024)
                        total_mb = total_size / (1024 * 1024)
                        
                        bar_length = 50
                        filled = int(bar_length * percent / 100)
                        bar = '█' * filled + '░' * (bar_length - filled)
                        
                        print(f'\r[{bar}] {percent:.1f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB)', end='', flush=True)
        
        print()  # New line after progress
        
    except (URLError, HTTPError) as e:
        raise Exception(f"Download failed: {e}")


def run_test_script():
    """Run the test script to verify the model works."""
    test_script = Path(__file__).parent / "test_mistral.py"
    
    if not test_script.exists():
        print(f"\n⚠ Warning: Test script not found at {test_script}")
        return False
    
    print(f"\n{'='*70}")
    print("Running model verification test...")
    print(f"{'='*70}\n")
    
    try:
        result = subprocess.run(
            [sys.executable, str(test_script)],
            capture_output=False,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Test failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        return False


def main():
    # Configuration - using bartowski's repository (more reliable)
    REPO_ID = "bartowski/Mistral-7B-Instruct-v0.3-GGUF"
    FILENAME = "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
    
    # Direct download URL from Hugging Face
    DOWNLOAD_URL = f"https://huggingface.co/{REPO_ID}/resolve/main/{FILENAME}"
    
    # Local directory
    script_dir = Path(__file__).parent.parent
    models_dir = script_dir / "resources" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    model_path = models_dir / FILENAME
    
    # Check if already exists
    if model_path.exists():
        file_size_mb = model_path.stat().st_size / (1024 * 1024)
        print(f"✓ Model already exists: {model_path}")
        print(f"  Size: {file_size_mb:.1f} MB")
        
        response = input("\nDo you want to re-download? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("Skipping download.")
            return str(model_path)
    
    # Download
    print(f"\n{'='*70}")
    print(f"Downloading Mistral-7B-Instruct v0.3 Q4_K_M")
    print(f"{'='*70}")
    print(f"Repository: {REPO_ID}")
    print(f"File: {FILENAME}")
    print(f"Size: ~4.37 GB")
    print(f"URL: {DOWNLOAD_URL}")
    print(f"{'='*70}\n")
    
    try:
        download_with_progress(DOWNLOAD_URL, model_path)
        
        # Verify download
        file_size_mb = model_path.stat().st_size / (1024 * 1024)
        file_size_gb = file_size_mb / 1024
        
        print(f"\n✓ Download complete!")
        print(f"  Location: {model_path}")
        print(f"  Size: {file_size_mb:.1f} MB ({file_size_gb:.2f} GB)")
        
        # Verify file size is reasonable (should be around 4.37 GB)
        if file_size_gb < 4.0 or file_size_gb > 5.0:
            print(f"\n⚠ Warning: File size seems incorrect (expected ~4.37 GB)")
            print(f"  The download may be incomplete or corrupted.")
            response = input("\nDo you want to keep this file? (y/N): ").strip().lower()
            if response not in ['y', 'yes']:
                model_path.unlink()
                print(f"  Removed file: {model_path}")
                sys.exit(1)
        
        return str(model_path)
        
    except KeyboardInterrupt:
        print("\n\n✗ Download cancelled by user")
        if model_path.exists():
            model_path.unlink()
            print(f"  Removed incomplete file: {model_path}")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n\n✗ Download failed: {e}")
        print("\n" + "="*70)
        print("ALTERNATIVE DOWNLOAD METHODS:")
        print("="*70)
        
        print("\n1. Manual Download:")
        print(f"   a) Visit: https://huggingface.co/{REPO_ID}/tree/main")
        print(f"   b) Find and click on: {FILENAME}")
        print(f"   c) Click the download button (⬇)")
        print(f"   d) Move the file to: {models_dir}")
        
        print("\n2. Using huggingface-cli:")
        print("   pip install huggingface-hub")
        print(f"   huggingface-cli download {REPO_ID} {FILENAME} \\")
        print(f"       --local-dir {models_dir} --local-dir-use-symlinks False")
        
        print("\n3. Using wget (if installed):")
        print(f"   wget {DOWNLOAD_URL} -O {model_path}")
        
        print("\n4. Using curl (if installed):")
        print(f"   curl -L {DOWNLOAD_URL} -o {model_path}")
        
        print("="*70 + "\n")
        
        if model_path.exists():
            model_path.unlink()
            print(f"Removed incomplete file: {model_path}\n")
        
        sys.exit(1)


if __name__ == "__main__":
    model_path = main()
    
    print(f"\n{'='*70}")
    print("NEXT STEPS:")
    print(f"{'='*70}")
    
    # Ask if user wants to run the test
    response = input("\nDo you want to test the model now? (Y/n): ").strip().lower()
    
    if response in ['', 'y', 'yes']:
        test_passed = run_test_script()
        
        if test_passed:
            print(f"\n{'='*70}")
            print("✓ Model verification successful!")
            print(f"{'='*70}")
            print("\nFinal steps:")
            print("1. Enable hybrid mode in config.yaml:")
            print("   improver: hybrid  # Change from 'lt' to 'hybrid'")
            print("\n2. Run the application:")
            print("   python runner.py")
            print(f"{'='*70}\n")
        else:
            print(f"\n{'='*70}")
            print("Model test failed. Please check:")
            print("1. llama-cpp-python is installed:")
            print("   pip install llama-cpp-python==0.2.90 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu")
            print("\n2. Run test manually:")
            print("   python scripts/test_mistral.py")
            print(f"{'='*70}\n")
    else:
        print("\n1. Verify the model works:")
        print("   python scripts/test_mistral.py")
        print("\n2. If llama-cpp-python is not installed:")
        print("   pip install llama-cpp-python==0.2.90 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu")
        print("\n3. Enable hybrid mode in config.yaml:")
        print("   improver: hybrid  # Change from 'lt' to 'hybrid'")
        print("\n4. Run the application:")
        print("   python runner.py")
        print(f"{'='*70}\n")
