# Windows Distribution

DYS-fr ships to clients as a conventional Windows installer: a wizard, a Start Menu
entry, an uninstaller, and an application that works offline the moment it is installed.

There are two build channels. The **installer** is what the client receives. The
**portable launcher** — a small executable that downloads its runtime on first launch —
is kept for testing and is no longer built by default.

## Installer channel (default)

`DYS-fr-Setup-<version>.exe` carries everything the application needs except the local
LLM model:

| Component | Approximate size |
|---|---|
| PyInstaller runtime (Python, Streamlit, spaCy, `llama_cpp`) | 334 MB |
| Embedded JRE | 363 MB |
| LanguageTool | 390 MB |
| spaCy `fr_core_news_md` | 63 MB |

That is roughly 1.15 GB installed, compressed into a setup executable of a few hundred
megabytes. The Mistral GGUF (4.1 GB) is **not** included: it would quadruple the
download to enable a mode that is not the default. Users who want hybrid mode download
the model from inside the application, which writes it to
`%LOCALAPPDATA%\DYS-fr\models` — a directory `src/utils/paths.py` already searches
before the bundled one.

### What the installer does

- Installs to `C:\Program Files\DYS-fr` (per-machine, one UAC prompt during setup).
- Creates a Start Menu entry, an uninstaller, and an optional desktop icon.
- Launches the app **as the original user**, not as the elevated installer, so runtime
  state lands in the right profile.
- On upgrade, detects a running instance through a named mutex and asks the user to
  close it before replacing files.

### Where things live after install

```
C:\Program Files\DYS-fr\
  DYS-fr-runtime.exe
  _internal\
    app.py, config.yaml, llama_cpp\...
    runtime\jre\bin\java.exe
    resources\languagetool\languagetool-server.jar
    resources\spacy\models\fr_core_news_md\

%LOCALAPPDATA%\DYS-fr\           (everything writable)
  config.yaml                    optional user override, merged over the bundled one
  models\                        downloaded GGUF files
  logs\                          dys-fr.log, languagetool.log
  run\                           single-instance lock and metadata
  spacy-cache\
```

The install directory is read-only at runtime. `packaging/windows/smoke_test.py`
enforces this by snapshotting the directory before launch and failing if anything under
it changed.

### Build prerequisites

- Python environment with `requirements-base.txt`, `requirements-build.txt` and
  `requirements-hybrid.txt` installed.
- **Inno Setup 6.3 or newer** (`ISCC.exe`). The build fails with a clear error if it is
  missing; it does not silently skip the installer.
- A redistributable JRE at `runtime/jre`, or passed via `DYS_FR_JRE_DIR` / `-JreDir`.
- Local LanguageTool assets under `resources/languagetool` and a spaCy model or wheel
  under `resources/spacy`.
- MinGW-w64 `gcc` is **not** needed for this channel.

### Build command

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\windows\build.ps1 `
  -Channel installer -IncludeAiRuntime -JreDir "C:\Program Files\Java\jdk-25"
```

`-IncludeAiRuntime` bundles the `llama_cpp` and `ollama` Python packages so hybrid mode
works once a model is downloaded. It does **not** stage the GGUF; that is
`-IncludeMistralModel`, which the installer channel refuses (the build fails if a model
is found in the stage root).

Output: `build/installer/DYS-fr-Setup-<version>.exe`, plus a
`DYS-fr-Setup-<version>-files.txt` manifest listing everything packed.

**Build time.** Both settings were measured on the same 4,880-file payload:

| Setting | Time | Installer size |
|---|---|---|
| Default (`lzma2/max`, solid) | **8 h 06 min** | 507 MB |
| `-FastCompression` (`lzma2/fast`, non-solid) | **88 seconds** | 572 MB |

That is 332x faster for 13% more download. Use `-FastCompression` for anything but a
final release build, and consider whether 65 MB is worth eight hours even then.

### Signing

There is no code-signing certificate yet, so the installer is unsigned and SmartScreen
will warn every user. `build.ps1` prints a warning per unsigned artefact and accepts
`-SignCertThumbprint` (and optionally `-SignToolExe`, `-SignTimestampUrl`) to sign both
the inner executable and the setup.

An ordinary OV certificate does not clear SmartScreen immediately — it accrues
reputation over weeks. Only an EV certificate is trusted on first use. Treat this as a
procurement lead time, not a build task.

## Portable channel (testing only)

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\windows\build.ps1 `
  -Channel portable -IncludeAiRuntime -IncludeMistralModel -JreDir "..."
```

Produces the lightweight `DYS-fr.exe` launcher plus component ZIPs and a manifest, to
be uploaded to a GitHub Release. The launcher downloads 5.19 GiB on first run, installs
next to itself, and refuses to run from a non-writable folder. This channel requires
MinGW-w64 `gcc`.

`-Channel both` builds both.

## Startup behaviour

The application starts Streamlit first and lets LanguageTool warm up behind it, so the
window appears in about five seconds rather than thirty. Until LanguageTool answers, the
interface shows an explicit "starting" message instead of a blank page.

If port 8501 is busy the app moves to a free port, logs the change, and shows the real
address in the sidebar. `instance.json` in `%LOCALAPPDATA%\DYS-fr\run` always records
the actual URLs.
