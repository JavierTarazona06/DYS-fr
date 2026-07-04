# Windows Release Checklist

For the installer channel, which is what the client receives. See
[windows_distribution.md](windows_distribution.md) for the portable channel.

## Pre-build

- Confirm the branch is the intended release branch.
- Confirm `resources/languagetool` exists and contains `languagetool-server.jar`.
- Confirm `resources/spacy` contains either `models/fr_core_news_md` or a `fr_core_news_md-*.whl`.
- Confirm a redistributable JRE is available at `runtime/jre` or through `DYS_FR_JRE_DIR` / `-JreDir`.
- Confirm **Inno Setup 6.3+** is installed (`ISCC.exe`), or pass `-IsccExe`.
- Confirm the environment has `requirements-build.txt` and `requirements-hybrid.txt` installed.
- Run the offline test suite: `pytest tests/test_installer_layout.py tests/test_model_downloader.py tests/test_windows_portable_packager.py -q`.

The Mistral GGUF is **not** required for this channel and must not be staged.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\windows\build.ps1 `
  -Channel installer -IncludeAiRuntime -JreDir "C:\Program Files\Java\jdk-25"
```

Verify:

- `build/staging/hybrid/staging-manifest.json` was created.
- `build/staging/hybrid/resources/models` does **not** exist (the build fails if it does).
- `build/pyinstaller-runtime/DYS-fr-runtime/DYS-fr-runtime.exe` exists.
- `build/installer/DYS-fr-Setup-<version>.exe` exists; note its size and SHA-256 (the build prints both).
- `build/installer/DYS-fr-Setup-<version>-files.txt` contains no `.gguf` entry.

## Smoke validation

On a clean VM with a snapshot to roll back to. Windows Sandbox is not available on
Windows 11 Home, so use a real VM.

Install with all defaults, then:

```powershell
.\.venv\Scripts\python.exe .\packaging\windows\smoke_test.py
```

The smoke test discovers the real ports from `%LOCALAPPDATA%\DYS-fr\run\instance.json`,
asserts the UI answers within 20 s and LanguageTool within 90 s, checks the installed
file layout, and fails if anything under the install directory changed while the app ran.

Confirm by hand what the smoke test cannot:

- The wizard runs to completion with a single UAC prompt.
- **Task Manager shows `DYS-fr-runtime.exe` running as the user, not elevated.** This is
  the `runasoriginaluser` flag; if it regresses, first-launch state goes to the
  administrator's profile and the app silently splits in two.
- A Start Menu entry and an uninstaller entry in Apps & Features exist.
- No console window flashes when LanguageTool starts.
- Launching as a **standard user** works, and state appears under that user's `%LOCALAPPDATA%`.
- **With the VM network disabled**, light mode corrects text end to end. This is the
  entire point of shipping a 1.2 GB installer; test it every release.
- Occupying port 8501 before launch produces a working app on another port, a warning in
  the sidebar, and the real URL in `instance.json`.
- Re-running the installer while the app is open prompts to close it.
- `%LOCALAPPDATA%\DYS-fr\logs\dys-fr.log` records the startup sequence.

## Model download

- The sidebar offers the model download only when no model is resolvable.
- Progress advances and the interface stays usable in light mode during the download.
- Cancelling keeps the `.part` file; restarting resumes rather than starting over.
- On completion, hybrid mode becomes selectable **without restarting the application**.

## Uninstall

- `DYS-fr-Setup-<version>.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART` exits 0.
- Uninstalling prompts about personal data and **defaults to keeping it**.
- `unins000.exe /VERYSILENT /KEEPDATA` removes the program; `models\` and `config.yaml` survive.
- `unins000.exe /VERYSILENT /PURGEDATA` removes `%LOCALAPPDATA%\DYS-fr` entirely.

## Release notes

- App version used in `build.ps1`.
- LanguageTool and spaCy versions from `packaging/windows/assets.manifest.json`.
- Detected JRE version from `build/staging/hybrid/staging-manifest.json`.
- Installer size and SHA-256.
- **Whether the build was signed.** An unsigned release needs SmartScreen guidance for
  the client, sent before delivery rather than during it.
