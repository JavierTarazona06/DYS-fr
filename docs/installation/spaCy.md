# spaCy Installation

Set up the French language pipeline required by the project.

## Prerequisites

- Python 3.9 or newer (use the same interpreter for every step)
- An up-to-date `pip` (`python -m pip install --upgrade pip`)
- Internet access to download the model (or an offline copy of the wheel)

---

## 1) Create the `.venv` virtual environment

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python --version
```

**Windows (PowerShell)**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate
python --version
```

---

## 2) Install project dependencies

With the virtual environment activated:

```bash
pip install -r requirements.txt
```

---

## 3) Download the French spaCy model wheel

**macOS / Linux**

```bash
python scripts/download_spacy.py
```

**Windows (PowerShell)**

```powershell
python .\scripts\download_spacy.py
```

This script:

- Fetches the download URL for `fr_core_news_md`
- Saves the wheel file into `resources/spacy/`
- Installs the wheel in the active Python environment (`python -m pip install --no-deps ...`)
- Runs `python -m spacy validate` to confirm the environment

Advanced usage:

```bash
python scripts/download_spacy.py --model fr_core_news_md --target-dir ./resources/spacy --force-reinstall
```

Use `--force-reinstall` when you want to overwrite the existing wheel on disk and reinstall the package in the current environment.

---

## 4) Install the downloaded model (optional)

If you used the helper script in step 3, the model wheel has already been installed.
Run the command below only if you skipped the script or need to reinstall manually:

```bash
pip install resources/spacy/fr_core_news_md-*.whl
```

On Windows PowerShell, the glob (`*`) expands automatically; if it does not, replace it with the exact filename.

---

## 5) Verify the installation

```bash
python -m spacy validate
```

The helper script already executes this check; rerun it if you changed your environment or want to double‑check. You should see `fr_core_news_md` listed as installed. You can also run:

```bash
python -c "import spacy; spacy.load('fr_core_news_md'); print('spaCy model ready ✔')"
```

---

### Alternative (online install)

If you have network access and do not need the wheel for reuse, you can skip step 3 and install the model directly:

```bash
python -m spacy download fr_core_news_md
```