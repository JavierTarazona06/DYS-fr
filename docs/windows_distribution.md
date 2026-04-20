# Windows Distribution

DYS-fr for Windows is distributed as a lightweight launcher plus downloadable runtime components.

Public release artifacts:

- `build/pyinstaller-dist/DYS-fr.exe`: lightweight launcher delivered to the client.
- `build/pyinstaller-dist/DYS-fr-components-<version>-hybrid.json`: component manifest consumed by the launcher.
- `build/pyinstaller-dist/DYS-fr-core-runtime-<version>-hybrid.zip`: PyInstaller runtime without heavy assets.
- `build/pyinstaller-dist/DYS-fr-jre-<version>.zip`: embedded Java runtime.
- `build/pyinstaller-dist/DYS-fr-languagetool-<version>.zip`: LanguageTool runtime.
- `build/pyinstaller-dist/DYS-fr-spacy-fr_core_news_md-<version>.zip`: French spaCy model.
- Mistral GGUF is downloaded directly from Hugging Face using the URL in the manifest.

On first launch, `DYS-fr.exe` checks whether `DYS-fr-runtime.exe`, `_internal/`, and `DYS-fr-runtime-manifest.json` already exist next to it. If the local installation is valid, it launches without internet. If anything is missing or incompatible, it downloads the component manifest, installs each required component, writes the installed manifest, and launches `DYS-fr-runtime.exe`.

If the launcher directory is not writable, DYS-fr shows a clear error asking the user to move `DYS-fr.exe` to a writable folder. It does not fall back to AppData because the portable contract is to keep `_internal` next to the executable.

## Runtime Design

- PyInstaller builds the real application runtime under `build/pyinstaller-runtime/DYS-fr-runtime`.
- The PyInstaller core runtime includes the app, Python, Streamlit, dependencies, and hybrid Python packages, but excludes the JRE, LanguageTool, spaCy model, and Mistral GGUF.
- `packaging/windows/package_portable.py` creates component ZIPs and `DYS-fr-components-<version>-hybrid.json`.
- `packaging/windows/portable_bootstrap.c` downloads via WinHTTP, validates SHA-256 with BCrypt, extracts ZIPs with PowerShell `Expand-Archive`, installs file components, and launches `DYS-fr-runtime.exe`.
- The installed layout keeps the existing paths: `_internal/runtime/jre`, `_internal/resources/languagetool`, `_internal/resources/spacy/models/fr_core_news_md`, and `_internal/resources/models`.

## Build Prerequisites

- Python environment with `requirements-base.txt`, `requirements-build.txt`, and `requirements-hybrid.txt` installed.
- MinGW-w64 `gcc` available on `PATH`, or pass `-GccExe`.
- Windows PowerShell with `Expand-Archive`.
- A redistributable JRE at `runtime/jre` or passed with `DYS_FR_JRE_DIR` / `-JreDir`.
- Local LanguageTool assets under `resources/languagetool`.
- Local spaCy wheel or extracted model under `resources/spacy`.
- Local Mistral GGUF under `resources/models` so the build can calculate its SHA-256 for the manifest.

## Build Command

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt -r requirements-hybrid.txt
powershell -ExecutionPolicy Bypass -File .\packaging\windows\build.ps1 -JreDir "C:\Program Files\Java\jdk-25" -IncludeHybrid
```

The default manifest URL compiled into the launcher is:

```text
https://github.com/JavierTarazona06/DYS-fr/releases/download/v<AppVersion>/DYS-fr-components-<AppVersion>-hybrid.json
```

Use `-ReleaseBaseUrl`, `-RuntimeManifestUrl`, or `-MistralUrl` to point at alternate release locations.

## Outputs

- Launcher: `build/pyinstaller-dist/DYS-fr.exe`
- Component manifest: `build/pyinstaller-dist/DYS-fr-components-<version>-hybrid.json`
- Core runtime ZIP: `build/pyinstaller-dist/DYS-fr-core-runtime-<version>-hybrid.zip`
- JRE ZIP: `build/pyinstaller-dist/DYS-fr-jre-<version>.zip`
- LanguageTool ZIP: `build/pyinstaller-dist/DYS-fr-languagetool-<version>.zip`
- spaCy ZIP: `build/pyinstaller-dist/DYS-fr-spacy-fr_core_news_md-<version>.zip`
- Intermediate PyInstaller runtime: `build/pyinstaller-runtime/DYS-fr-runtime`
- Staged asset payload: `build/staging/hybrid`

Upload the JSON and GitHub-hosted ZIPs to the matching public GitHub Release before distributing the launcher. The Mistral URL in the manifest points to Hugging Face.

## Smoke Test

After publishing release assets:

```powershell
.\.venv\Scripts\python.exe .\packaging\windows\smoke_test.py --exe .\build\pyinstaller-dist\DYS-fr.exe
```

For local testing, keep the generated component JSON and ZIPs next to `DYS-fr.exe`; the launcher will prefer adjacent component files before downloading.
