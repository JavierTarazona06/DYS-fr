# 🛠️ Installation & Setup Guide

This guide covers the complete setup for **DYS-fr**, including the Python environment, core NLP engines (LanguageTool, spaCy), and local AI models (Mistral or Gemma).

---

## ✅ Prerequisites

*   **Operating System:** Windows, macOS, or Linux.
*   **Python:** Version 3.9 or higher.
*   **Java Runtime:** Version 17 or higher (Required for LanguageTool).
    *   Verify with: `java -version`
*   **RAM:**
    *   *Basic Mode (Rules only):* 4 GB minimum.
    *   *Hybrid Mode (AI):* 8 GB minimum recommended.

---

## 1. Environment Setup

Create a virtual environment to keep dependencies isolated.

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
python -V  # Should output Python 3.9+
```

### Windows (PowerShell)
```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate
python -V  # Should output Python 3.9+
```

---

## 2. Install Core Dependencies

Install the base libraries required for the UI and rule-based checking.

```bash
pip install -r requirements.txt
```

---

## 3. Install NLP Engines (Mandatory)

DYS-fr relies on two offline engines for basic corrections and entity protection.

### A. LanguageTool (Grammar Server)
We use a helper script to download the standalone Java server.

**Run the download script:**
```bash
python scripts/download_languagetool.py
```
*   **What this does:** Downloads `LanguageTool-server.jar`, extracts it to `./resources/languagetool/`, and cleans up zip files.

### B. spaCy (Entity Protection)
We need the French language model (`fr_core_news_md`) to detect names and dates.

**Run the download script:**
```bash
python scripts/download_spacy.py
```
*   **What this does:** Downloads the `.whl` model file to `./resources/spacy/` and installs it into your virtual environment.
*   **Verify:** Run `python -m spacy validate` to confirm it is active.

---

## 4. Install AI Models (Choose One or Both)

To use the **"Intelligent (Hybrid)"** mode, you need an LLM. You can choose between **Mistral** (fully embedded) or **Gemma** (via Ollama).

### Option A: Mistral 7B (Embedded)
*Best for: Zero-dependency setups (everything contained in the folder).*

1.  **Install the runtime:**
    ```bash
    pip install llama-cpp-python --prefer-binary
    ```
2.  **Download the Model:**
    ```bash
    python scripts/download_mistral.py
    ```
    *   This downloads `Mistral-7B-Instruct-v0.3-Q4_K_M.gguf` (~4.0 GB) to `./resources/models/`.


### Option B: Gemma 3
*Best for: Performance, speed, and easy setup.*

1.  **Download Ollama:** Visit [ollama.com](https://ollama.com) and install it.
2.  **Pull the Model:** Open your terminal and run:
    ```bash
    ollama pull gemma3:4b
    ```
3.  **Install Python Connector:**
    ```bash
    pip install ollama
    ```

---

## 5. Run the Application

Once everything is installed, launch the orchestrator. This will start the LanguageTool server in the background and launch the Streamlit UI.

```bash
python runner.py
```

The application should open automatically in your browser at `http://localhost:8501`.

---

## 🛠️ Troubleshooting

**"Java not found" or "LanguageTool failed to start"**
*   Ensure Java 17+ is installed and added to your system PATH.
*   Check `config.yaml` to see if `jre_bin` is set to `"java"`.

**"Model not found" (Mistral)**
*   Ensure the `.gguf` file exists in `resources/models/`.
*   Run `python scripts/test_mistral.py` to verify the file integrity.

**"Connection refused" (Gemma/Ollama)**
*   Ensure Ollama is running in the background.
*   Run `ollama serve` in a separate terminal window.

**"Visual C++ Build Tools missing" (Windows)**
*   If `pip install llama-cpp-python` fails, install the [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) (C++ workload).