# DYS-fr
Offline French text improver tailored for dyslexia (DYS). Built with Streamlit, LanguageTool, Hunspell, and spaCy, it applies safe corrections (orthography, punctuation, segmentation) with strict guardrails. Features accessible UI, diff view, high-contrast mode, and packaged Windows installer.

This project delivers an offline text correction and simplification tool designed specifically for French texts and optimized for people with dyslexia (DYS).

# Key features:

- Accessible UI (Streamlit): dyslexia-friendly fonts (Lexend, Atkinson Hyperlegible, OpenDyslexic), adjustable font size, line spacing, high-contrast mode, and distraction-free focus mode.

- Correction engine (DYS-safe): based on LanguageTool and Hunspell, with strict filters (“guardrails”) to ensure no new information (dates, numbers, names, entities) is added. Only safe corrections are applied (orthography, accents, punctuation, light reordering, or splitting long sentences).

- Quality assurance: includes curated test sets with real/simulated dyslexic errors, metrics on error reduction (≥80%), sentence length, readability, and validation with end users.

- Packaged for Windows: fully offline with embedded Java Runtime, LanguageTool, Hunspell, and spaCy. Distributed via PyInstaller + Inno Setup installer.

- Safe by design: strict “no-additions” policy (no invented connectors, entities, or paraphrases). Guardrails prevent unsafe edits.

# Intended workflow:

1. User pastes French text.
2. Clicks “Améliorer”.
3. Tool applies safe corrections.
4. User sees a diff view (red/green) and the final improved text.
