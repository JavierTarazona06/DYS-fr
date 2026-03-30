# Windows Release Checklist

## Pre-build

- Confirm the branch is `feature/windows-distribution` or the intended release branch.
- Confirm `resources/languagetool` exists and contains `languagetool-server.jar`.
- Confirm `resources/spacy` contains either the extracted `fr_core_news_md` model directory or the wheel.
- Confirm a redistributable JRE is available at `runtime/jre` or through `DYS_FR_JRE_DIR`.
- Confirm the build environment has `requirements-base.txt` and `requirements-build.txt` installed.

## Build

- Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\windows\build.ps1 -JreDir C:\path\to\jre
```

- Verify `build/staging/basic/staging-manifest.json` was created.
- Verify `build/pyinstaller-dist/DYS-fr/DYS-fr.exe` exists.
- Verify the Inno Setup step completed if `ISCC.exe` is installed.

## Smoke validation

- Run:

```powershell
.\.venv\Scripts\python.exe .\packaging\windows\smoke_test.py --exe .\build\pyinstaller-dist\DYS-fr\DYS-fr.exe
```

- Confirm the smoke test reports HTTP `200`.
- Confirm the packaged executable terminates cleanly after the smoke test.

## Clean-machine validation

- Install the generated `Setup.exe` on a Windows machine without Python or system Java.
- Launch the app from the Start Menu.
- Confirm the browser opens to the local app and the UI loads.
- Confirm basic correction works offline.
- Confirm hybrid mode is hidden in the basic installer when optional runtimes are absent.
- Confirm uninstall completes and the app binaries are removed from `Program Files`.

## Release notes

- Record the app version used in `build.ps1`.
- Record the LanguageTool version and spaCy model version from `packaging/windows/assets.manifest.json`.
- Record the detected JRE version from `build/staging/basic/staging-manifest.json`.
- Record whether the artifact is `basic` or `basic + hybrid`.
