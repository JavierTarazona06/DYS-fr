# DYS-fr
Offline French text improver tailored for dyslexia (DYS). Built with Streamlit, LanguageTool and spaCy, it applies safe corrections (orthography, punctuation, segmentation). Ships as a packaged Windows installer that works with no internet connection.

This project delivers an offline text correction and simplification tool designed specifically for French texts and optimized for people with dyslexia (DYS).

> **Status.** Items marked 🚧 are specified and planned but **not implemented yet**.
> [docs/completion-plan.md](docs/completion-plan.md) is the plan to close them;
> [docs/business-rules.md](docs/business-rules.md) records the implementation status of
> every documented rule, one by one.

# Key features:

- Accessible UI (Streamlit): 🚧 dyslexia-friendly fonts (Lexend, Atkinson Hyperlegible, OpenDyslexic), 🚧 adjustable font size, 🚧 line spacing, 🚧 high-contrast mode, and 🚧 distraction-free focus mode.

- Correction engine (DYS-safe): based on LanguageTool, with filters (“guardrails”) intended to ensure no new information (dates, numbers, names, entities) is added. Entity protection is in place; 🚧 the remaining validation layer is not yet wired in. Only safe corrections are applied (orthography, accents, punctuation, 🚧 splitting long sentences). Hunspell is listed in the design documents but is not part of the current engine.

- Quality assurance: 🚧 curated test sets with simulated dyslexic errors and metrics on error reduction (≥80%), sentence length and readability. Validation with end users is a separate, non-engineering task.

- Packaged for Windows: fully offline with embedded Java Runtime, LanguageTool and spaCy. Distributed via PyInstaller + Inno Setup installer.

- Safe by design: a strict “no-additions” policy (no invented connectors, entities, or paraphrases) is the product's central commitment. 🚧 It is currently enforced only by entity masking; the full guardrail layer is the next milestone.

# Intended workflow:

1. User pastes French text.
2. Clicks “Améliorer”.
3. Tool applies safe corrections.
4. User sees a diff view (red/green) and the final improved text.

# Install on Windows

Run `DYS-fr-Setup-<version>.exe` and click through the wizard. It installs to
`C:\Program Files\DYS-fr` and creates a Start Menu entry and an uninstaller.

Everything the application needs ships inside the installer — Python, Streamlit,
LanguageTool, an embedded Java runtime and the French spaCy model — so once installed
it runs with no internet connection at all.

The optional local AI model (Mistral 7B, 4.1 GB) is **not** included. Download it from
the sidebar inside the application if you want the hybrid mode; it is saved to
`%LOCALAPPDATA%\DYS-fr\models` and the download can be cancelled and resumed.

## Uninstall and reinstall

Uninstall from the Start Menu (**DYS-fr → Désinstaller DYS-fr**) or from
**Settings → Apps**. You are asked whether to also delete your personal data — the
downloaded model and your preferences — and the answer defaults to keeping it, so
reinstalling later does not mean downloading 4 GB again.

To reinstall, just run the setup executable again.

Silent equivalents, for scripting:

```powershell
DYS-fr-Setup-0.1.0.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
"C:\Program Files\DYS-fr\unins000.exe" /VERYSILENT /KEEPDATA
```

Use `/PURGEDATA` instead of `/KEEPDATA` to also remove `%LOCALAPPDATA%\DYS-fr`.

# Build the installer

You need a Python 3.11 virtual environment with `requirements-build.txt` and
`requirements-hybrid.txt` installed, **Inno Setup 6.3 or newer**, a JDK 17 or newer,
and the assets under `resources/` (see [docs/installation.md](docs/installation.md)).

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\windows\build.ps1 -Channel installer -IncludeAiRuntime -FastCompression -JreDir "C:\Program Files\Java\jdk-25"
```

The result appears in `build/installer/`, and the script prints its size and SHA-256.

`-IncludeAiRuntime` bundles the local-LLM engine so hybrid mode works once a model is
downloaded; it does not put the 4 GB model in the installer.

Drop `-FastCompression` for a release build. Measured on the same payload, it is the
difference between a **572 MB installer in 88 seconds** and a **507 MB installer in
8 hours**, so use the fast setting for everything except a final release.

Full details, including the portable channel and code signing:
[docs/windows_distribution.md](docs/windows_distribution.md).
