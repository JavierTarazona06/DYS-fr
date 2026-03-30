# Windows Distribution

This repository includes a packaging flow for a professional Windows release with:

- a one-folder PyInstaller application bundle;
- staged offline assets for basic mode;
- an Inno Setup installer for a standard wizard experience.

## Runtime design

- The packaged executable uses `runner.py` as the entrypoint and delegates startup to `src/runtime/launcher.py`.
- Streamlit runs in-process instead of `python -m streamlit`, which is safer for frozen execution.
- LanguageTool is started through `src/runtime/languagetool.py` and prefers a bundled JRE under `runtime/jre`.
- spaCy loads the French model from an extracted offline model directory under `resources/spacy/models/fr_core_news_md`, with wheel fallback if needed.
- Optional Mistral models are searched in both `resources/models` and `%LOCALAPPDATA%\DYS-fr\models`.

## Build prerequisites

- Python environment with `requirements-base.txt` and `requirements-build.txt` installed.
- A redistributable JRE directory available locally. The build script expects either:
  - `runtime/jre` already present in the repository root, or
  - `DYS_FR_JRE_DIR` pointing at a JRE root that contains `bin/java.exe`.
- Local LanguageTool assets under `resources/languagetool`.
- Local spaCy wheel under `resources/spacy`.

## Build commands

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-base.txt -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File .\packaging\windows\build.ps1 -JreDir C:\path\to\jdk-17-jre
```

Optional hybrid payload:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\windows\build.ps1 -JreDir C:\path\to\jdk-17-jre -IncludeHybrid
```

## Outputs

- Staged runtime payload: `build/staging/basic`
- PyInstaller bundle: `build/pyinstaller-dist/DYS-fr`
- Inno Setup installer: `build/installer`

If Inno Setup is not installed, the build script still produces the PyInstaller bundle and skips only the installer step.

## Smoke test

After a successful build, validate the packaged executable:

```powershell
.\.venv\Scripts\python.exe .\packaging\windows\smoke_test.py --exe .\build\pyinstaller-dist\DYS-fr\DYS-fr.exe
```

The smoke test starts the packaged executable, waits for the local HTTP endpoint to answer with `200`, and then shuts the process tree down cleanly.

## Basic vs hybrid distribution

- Basic installer:
  - bundles Python, Streamlit, LanguageTool, spaCy model, and embedded JRE;
  - does not bundle Mistral;
  - hides hybrid mode when optional AI runtimes are not installed.
- Hybrid add-on:
  - can stage the Mistral GGUF with `-IncludeHybrid`;
  - still keeps Gemma as an external Ollama integration.
