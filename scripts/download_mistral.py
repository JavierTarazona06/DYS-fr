#!/usr/bin/env python3
"""
Download Mistral-7B-Instruct v0.3 Q4_K_M model from Hugging Face.
This script works on any machine with Python and internet connection.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path
from urllib.request import urlretrieve


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
    urlretrieve(url, destination, reporthook=report_progress)
    print()  # New line after progress


def get_python_version():
    """Get Python version in format like '3.12', '3.11', etc."""
    version_info = sys.version_info
    return f"{version_info.major}.{version_info.minor}"


def get_llama_cpp_wheel_url():
    """Get the appropriate wheel URL for llama-cpp-python from GitHub Releases."""
    python_version = get_python_version()
    system = platform.system()
    
    # Map Python version to wheel version code
    version_map = {
        "3.11": "cp311",
        "3.12": "cp312",
        "3.10": "cp310",
    }
    
    cp_version = version_map.get(python_version)
    if not cp_version:
        return None
    
    # For Windows x64
    if system == "Windows":
        wheel_filename = f"llama_cpp_python-0.3.2-{cp_version}-{cp_version}-win_amd64.whl"
        wheel_url = f"https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.2/{wheel_filename}"
        return wheel_url
    
    # Add other platforms if needed (Linux, macOS)
    return None


def install_llama_cpp_python():
    """Attempt to install llama-cpp-python using pre-built wheel from GitHub."""
    print(f"\n{'='*60}")
    print("Installing llama-cpp-python")
    print(f"{'='*60}")
    
    python_version = get_python_version()
    print(f"Detected Python version: {python_version}")
    print(f"Platform: {platform.system()}")
    
    # Try using wheel from GitHub Releases
    wheel_url = get_llama_cpp_wheel_url()
    
    if wheel_url:
        print(f"\nOption 1: Using pre-built wheel from GitHub Releases")
        print(f"URL: {wheel_url}")
        response = input("\nTry this installation method? (Y/n): ").strip().lower()
        
        if response in ['', 'y', 'yes']:
            try:
                print("\nInstalling from wheel...")
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", wheel_url],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print("✓ Installation successful!")
                    return True
                else:
                    print(f"✗ Installation failed: {result.stderr}")
                    print("\nTrying alternative method...")
            except Exception as e:
                print(f"✗ Error: {e}")
                print("\nTrying alternative method...")
    
    # Fallback to standard pip install
    print(f"\nOption 2: Standard pip installation with pre-built binary")
    response = input("Try standard installation? (Y/n): ").strip().lower()
    
    if response in ['', 'y', 'yes']:
        try:
            print("\nInstalling llama-cpp-python...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "llama-cpp-python", "--prefer-binary"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print("✓ Installation successful!")
                return True
            else:
                print(f"✗ Installation failed: {result.stderr}")
        except Exception as e:
            print(f"✗ Error: {e}")
    
    print("\n" + "="*60)
    print("MANUAL INSTALLATION INSTRUCTIONS:")
    print("="*60)
    print("For Python 3.12, Windows x64:")
    print("pip install https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.2/llama_cpp_python-0.3.2-cp312-cp312-win_amd64.whl")
    print("\nFor Python 3.11, Windows x64:")
    print("pip install https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.2/llama_cpp_python-0.3.2-cp311-cp311-win_amd64.whl")
    print("\nOr use standard installation:")
    print("pip install llama-cpp-python --prefer-binary")
    print("="*60 + "\n")
    
    return False


def download_with_huggingface_hub(repo_id: str, filename: str, local_dir: Path):
    """Download using huggingface_hub library."""
    try:
        from huggingface_hub import hf_hub_download
        
        print("Using huggingface_hub for download...")
        local_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(local_dir),
            local_dir_use_symlinks=False
        )
        return file_path
    except ImportError:
        print("✗ huggingface_hub not installed")
        print("\nInstalling huggingface_hub...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "huggingface_hub"],
                check=True,
                capture_output=True
            )
            print("✓ huggingface_hub installed successfully")
            return download_with_huggingface_hub(repo_id, filename, local_dir)
        except Exception as e:
            print(f"✗ Failed to install huggingface_hub: {e}")
            return None
    except Exception as e:
        print(f"✗ Download failed: {e}")
        return None


def main():
    # Configuration - Using alternative repository that's publicly accessible
    # Option 1: bartowski's quantized models (more recent and accessible)
    REPO_ID = "bartowski/Mistral-7B-Instruct-v0.3-GGUF"
    FILENAME = "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
    
    # Option 2: If bartowski doesn't work, try MaziyarPanahi
    FALLBACK_REPO = "MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF"
    FALLBACK_FILENAME = "Mistral-7B-Instruct-v0.3.Q4_K_M.gguf"
    
    BASE_URL = "https://huggingface.co"
    
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
    print(f"\n{'='*60}")
    print(f"Downloading Mistral-7B-Instruct v0.3 Q4_K_M")
    print(f"{'='*60}")
    print(f"From: {REPO_ID}")
    print(f"File: {FILENAME}")
    print(f"Size: ~4.37 GB")
    print(f"{'='*60}\n")
    
    # Try using huggingface_hub first (most reliable method)
    print("Method 1: Using huggingface_hub library (recommended)")
    downloaded_path = download_with_huggingface_hub(REPO_ID, FILENAME, models_dir)
    
    if downloaded_path:
        file_size_mb = Path(downloaded_path).stat().st_size / (1024 * 1024)
        print(f"\n✓ Download complete!")
        print(f"  Location: {downloaded_path}")
        print(f"  Size: {file_size_mb:.1f} MB")
        return str(downloaded_path)
    
    # Try fallback repository
    print(f"\nTrying fallback repository: {FALLBACK_REPO}")
    fallback_path = models_dir / FALLBACK_FILENAME
    downloaded_path = download_with_huggingface_hub(FALLBACK_REPO, FALLBACK_FILENAME, models_dir)
    
    if downloaded_path:
        file_size_mb = Path(downloaded_path).stat().st_size / (1024 * 1024)
        print(f"\n✓ Download complete!")
        print(f"  Location: {downloaded_path}")
        print(f"  Size: {file_size_mb:.1f} MB")
        return str(downloaded_path)
    
    # If all methods failed, show manual instructions
    print(f"\n\n✗ Automatic download failed!")
    print("\n" + "="*60)
    print("MANUAL DOWNLOAD INSTRUCTIONS:")
    print("="*60)
    print(f"Option 1: Using huggingface-cli")
    print(f"   huggingface-cli download {REPO_ID} {FILENAME} --local-dir {models_dir}")
    print(f"\nOption 2: Browser download")
    print(f"   1. Visit: {BASE_URL}/{REPO_ID}")
    print(f"   2. Click 'Files and versions' tab")
    print(f"   3. Download: {FILENAME}")
    print(f"   4. Move to: {models_dir}")
    print(f"\nOption 3: Try alternative repository")
    print(f"   huggingface-cli download {FALLBACK_REPO} {FALLBACK_FILENAME} --local-dir {models_dir}")
    print("="*60 + "\n")
    
    sys.exit(1)


if __name__ == "__main__":
    model_path = main()
    print(f"\n{'='*60}")
    print("Next steps:")
    print(f"{'='*60}")
    
    # Ask if user wants to install llama-cpp-python
    response = input("\nDo you want to install llama-cpp-python now? (Y/n): ").strip().lower()
    
    if response in ['', 'y', 'yes']:
        success = install_llama_cpp_python()
        if success:
            print("\n✓ Setup complete!")
            print("\nYou can now test the model:")
            print("   python scripts/test_mistral.py")
        else:
            print("\n⚠ Please install llama-cpp-python manually before testing.")
    else:
        print("\n1. Install llama-cpp-python:")
        print("   pip install llama-cpp-python --prefer-binary")
        print("\n   Or use pre-built wheel:")
        python_version = get_python_version()
        wheel_url = get_llama_cpp_wheel_url()
        if wheel_url:
            print(f"   pip install {wheel_url}")
        print("\n2. Test the model:")
        print("   python scripts/test_mistral.py")
    
    print(f"{'='*60}\n")
