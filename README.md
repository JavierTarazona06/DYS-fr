# DYS-fr
Offline French text improver tailored for dyslexia (DYS). Built with Streamlit, LanguageTool and spaCy, it applies safe corrections (orthography, punctuation, segmentation). Ships as a packaged Windows installer that works with no internet connection.

This project delivers an offline text correction and simplification tool designed specifically for French texts and optimized for people with dyslexia (DYS).

> **Status.** Items marked 🚧 are specified and planned but **not implemented yet**.
> [docs/completion-plan.md](docs/completion-plan.md) is the plan to close them;
> [docs/business-rules.md](docs/business-rules.md) records the implementation status of
> every documented rule, one by one.

# Key features:

- Accessible UI (Streamlit): adjustable font size, line spacing and a distraction-free focus mode, saved per user; 🚧 dyslexia-friendly fonts (Lexend, Atkinson Hyperlegible, OpenDyslexic) and 🚧 high-contrast mode.

- Correction engine (DYS-safe): based on LanguageTool, with an optional local LLM (hybrid mode). Every correction passes a final set of checks ("guardrails") before it reaches the user: no new entities, proper nouns, numbers or dates, no invented words, no word the user wrote dropped or swapped, and at most 12% new content words. If a hybrid-mode rewrite fails them, the user gets the rule-based correction instead. Only safe corrections are applied (orthography, accents, punctuation, word segmentation; 🚧 splitting long sentences). Hunspell is listed in the design documents but is not part of the current engine.

- Quality assurance: a corpus of 30 French texts with simulated dyslexic errors, measuring illegal additions, error reduction, sentence length and readability on every run. In light mode it currently records 0 illegal additions and an 87% error reduction on the fixed corpus; readability does not yet improve, since that needs sentence splitting. Validation with end users is a separate, non-engineering task.

- Packaged for Windows: fully offline with embedded Java Runtime, LanguageTool and spaCy. Distributed via PyInstaller + Inno Setup installer.

- Safe by design: a strict “no-additions” policy (no invented connectors, entities, or paraphrases) is the product's central commitment, enforced by the guardrails above in both modes. Where a rule can only be approximated after the fact, [docs/business-rules.md](docs/business-rules.md) says so.

# Intended workflow:

1. User pastes French text.
2. Clicks “Corriger”.
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
