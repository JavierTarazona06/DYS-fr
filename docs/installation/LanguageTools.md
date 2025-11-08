# LanguageTool Installation
Setup & Run (Markdown)

## Prerequisites

* **Python 3.9+**
* **Java 17+** (`java -version` should show 17 or newer)

---

## 1) Create the `.venv` virtual environment

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -V
```

**Windows (PowerShell)**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate
python -V
```

---

## 2) Install dependencies

```bash
pip install -r requirements.txt
```

---

## 3) Download & prepare LanguageTool (Python script)

**macOS / Linux**

```bash
python scripts/download_languagetool.py
```

**Windows (PowerShell)**

```powershell
python .\scripts\download_languagetool.py
```

This will:

* Download `LanguageTool-latest-snapshot.zip` from the internal snapshot URL
* Extract it to a temp directory
* Rename the extracted folder to `LanguageTool-6.7` at the project root
* Delete the `.zip`

---

## 4) Run the app

From the project root (with the venv activated):

```bash
python -m main
```

(or `python main.py`)