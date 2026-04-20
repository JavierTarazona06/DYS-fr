# Windows Release Checklist

## Pre-build

- Confirm the branch is the intended release branch.
- Confirm `resources/languagetool` exists and contains `languagetool-server.jar`.
- Confirm `resources/spacy` contains either `models/fr_core_news_md` or a `fr_core_news_md-*.whl`.
- Confirm `resources/models/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf` exists so the manifest can record its size and SHA-256.
- Confirm a redistributable JRE is available at `runtime/jre` or through `DYS_FR_JRE_DIR` / `-JreDir`.
- Confirm MinGW-w64 `gcc` is available, or pass `-GccExe`.
- Confirm the environment has `requirements-build.txt` and `requirements-hybrid.txt` installed.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\windows\build.ps1 -JreDir "C:\Program Files\Java\jdk-25" -IncludeHybrid
```

Verify:

- `build/staging/hybrid/staging-manifest.json` was created.
- `build/pyinstaller-runtime/DYS-fr-runtime/DYS-fr-runtime.exe` exists as the intermediate core runtime.
- `build/pyinstaller-dist/DYS-fr.exe` exists and is a lightweight launcher.
- `build/pyinstaller-dist/DYS-fr-components-0.1.0-hybrid.json` exists and contains `components[]`.
- `build/pyinstaller-dist/DYS-fr-core-runtime-0.1.0-hybrid.zip` exists and does not contain JRE, LanguageTool, spaCy model, or Mistral.
- `build/pyinstaller-dist/DYS-fr-jre-0.1.0.zip` exists.
- `build/pyinstaller-dist/DYS-fr-languagetool-0.1.0.zip` exists.
- `build/pyinstaller-dist/DYS-fr-spacy-fr_core_news_md-0.1.0.zip` exists.
- The Mistral component in the JSON points to Hugging Face and records the local GGUF size and SHA-256.

## GitHub Release

- Create or update the public GitHub Release matching `v<AppVersion>`.
- Upload the component manifest JSON.
- Upload the core, JRE, LanguageTool, and spaCy ZIPs.
- Confirm each GitHub URL in the manifest is public and downloadable without authentication.
- Confirm the Mistral URL points to the Hugging Face GGUF.

## Smoke Validation

Run after publishing release assets:

```powershell
.\.venv\Scripts\python.exe .\packaging\windows\smoke_test.py --exe .\build\pyinstaller-dist\DYS-fr.exe --timeout 900
```

For local pre-release testing, keep the generated JSON and ZIPs next to `DYS-fr.exe`; the launcher will use adjacent files before downloading. Mistral will still download from the URL in the manifest unless the GGUF file is also next to `DYS-fr.exe`.

Confirm:

- First launch installs `DYS-fr-runtime.exe`, `_internal/`, and `DYS-fr-runtime-manifest.json`.
- First launch downloads all missing required components, including Mistral.
- Second launch starts without redownloading when local files are valid.
- Deleting a critical file causes only the missing component to be repaired.
- First launch without internet shows a clear error.
- Launch after valid installation works without internet.
- Running from a non-writable folder shows a clear error asking the user to move the executable.
- Streamlit responds with HTTP 200.
- LanguageTool responds at `/v2/languages`.
- The IA mode is available and detects Mistral.

## Release Notes

- Record the app version used in `build.ps1`.
- Record the payload flavor: `hybrid` for the client release.
- Record LanguageTool and spaCy versions from `packaging/windows/assets.manifest.json`.
- Record the detected JRE version from `build/staging/hybrid/staging-manifest.json`.
- Record final launcher size, component sizes, and SHA-256 values.
