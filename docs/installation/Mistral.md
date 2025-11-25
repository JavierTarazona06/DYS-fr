# Mistral-7B-Instruct v0.3 Installation Guide

This guide explains how to install and configure Mistral-7B-Instruct v0.3 (Q4_K_M quantized) for the DYS-fr project.

## Prerequisites

- Python 3.10 or higher
- At least 6 GB of free RAM
- ~5 GB of free disk space for the model
- Active internet connection (for initial download)

---

## Installation Steps

### 1. Download the Model

**Option A: Automated Download (Recommended)**

Run the download script:

```bash
python scripts/download_mistral.py
```

This will download `mistral-7b-instruct-v0.3.Q4_K_M.gguf` (~4.37 GB) to `resources/models/`.

**Option B: Manual Download**

1. Visit: https://huggingface.co/bartowski/Mistral-7B-Instruct-v0.3-GGUF/tree/main
2. Find and download: `Mistral-7B-Instruct-v0.3-Q4_K_M.gguf`
3. Move the file to: `resources/models/`

---

### 2. Install llama-cpp-python

**Option A: Install from requirements.txt (Recommended)**

```bash
pip install -r requirements.txt
```

**Option B: Install Directly**

```bash
pip install llama-cpp-python==0.2.90 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
```

This installs a precompiled CPU-only version (no compilation needed).

---

### 3. Verify Installation

Run the test script to ensure everything works:

```bash
python scripts/test_mistral.py
```

**Expected output:**

```
============================================================
Testing Mistral-7B-Instruct v0.3 Q4_K_M
============================================================
Model: mistral-7b-instruct-v0.3.Q4_K_M.gguf
Size: 4.37 GB
============================================================

Loading model (this may take a moment)...
✓ Model loaded successfully!

Response:
============================================================
Je mange une pomme à Paris. C'est très bon.
============================================================

✓ Test completed successfully!
```

---

## Configuration

The model is configured in `config.yaml`:

```yaml
llm:
  model: mistral-7b-q4
  models_dir: resources/models
  
  mistral:
    filename: mistral-7b-instruct-v0.3.Q4_K_M.gguf
    n_ctx: 4096        # Context window (reduce to 2048 if RAM < 6 GB)
    max_tokens: 512    # Max generation length
    temperature: 0.3   # Lower = more deterministic
```

---

## Usage in Application

To enable hybrid mode (LanguageTool + LLM):

1. Edit `config.yaml`:
   ```yaml
   improver: hybrid  # Change from "lt" to "hybrid"
   ```

2. Run the application:
   ```bash
   python runner.py
   ```

---

## Memory Requirements

| Configuration | RAM Usage | Recommended For |
|--------------|-----------|-----------------|
| `n_ctx: 4096` | ~5.5-6 GB | Systems with ≥8 GB RAM |
| `n_ctx: 2048` | ~4.5-5 GB | Systems with 6-8 GB RAM |
| `n_ctx: 1024` | ~4-4.5 GB | Systems with 4-6 GB RAM |

---

## Troubleshooting

### Issue: "Model not found"

**Solution:** Verify the model is in the correct location:
```bash
ls resources/models/mistral-7b-instruct-v0.3.Q4_K_M.gguf
```

### Issue: "Out of memory"

**Solution:** Reduce context window in `config.yaml`:
```yaml
mistral:
  n_ctx: 2048  # or 1024 for very low RAM
```

### Issue: "llama-cpp-python not installed"

**Solution:** Install the precompiled version:
```bash
pip install llama-cpp-python --prefer-binary
```

---

## Alternative Models

If Mistral-7B is too large for your system, consider:

- **Gemma 3 4B** (~2.5 GB RAM) - Already configured in `config.yaml`
- **Phi-3 Mini** (~2 GB RAM) - Smaller but decent quality

Change model in `config.yaml`:
```yaml
llm:
  model: gemma3-4b  # Instead of mistral-7b-q4
```

---

## Performance Tips

1. **CPU Threads:** Adjust in `llm_improver.py` initialization:
   ```python
   n_threads=4  # Match your CPU core count
   ```

2. **Memory Mapping:** For systems with limited RAM:
   ```python
   use_mlock=False  # Disable memory locking
   use_mmap=True    # Enable memory mapping
   ```

3. **Batch Processing:** Process shorter texts for faster responses

---

## References

- [Mistral AI Official](https://mistral.ai/)
- [llama.cpp Documentation](https://github.com/ggerganov/llama.cpp)
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python)