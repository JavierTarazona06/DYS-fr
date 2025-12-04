#!/usr/bin/env python
"""
Quick sanity check for spaCy and the configured model.

- Reads spaCy model name from config.yaml via src.utils.config.load_config
- Confirms spaCy is importable and reports its version
- Attempts to load the configured model and run a tiny doc
- Exits with code 0 on success, 1 on failure
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import load_config  # noqa: E402


def main() -> int:
    try:
        import spacy  # type: ignore
        from spacy.util import get_package_path, is_package
    except Exception as exc:  # pragma: no cover - runtime check
        print(f"Failed to import spaCy: {exc}", file=sys.stderr)
        return 1

    cfg = load_config()
    model_name = cfg.get("spacy", {}).get("model") or "fr_core_news_md"
    print(f"spaCy version: {spacy.__version__}")
    print(f"Configured model: {model_name}")

    pkg_installed = is_package(model_name)
    print(f"Model installed (spaCy is_package): {pkg_installed}")

    if pkg_installed:
        try:
            pkg_path = get_package_path(model_name)
            print(f"Model package path: {pkg_path}")
        except Exception as exc:  # pragma: no cover - runtime check
            print(f"Could not resolve package path: {exc}", file=sys.stderr)

    try:
        nlp = spacy.load(model_name)
    except Exception as exc:  # pragma: no cover - runtime check
        print(f"Failed to load model '{model_name}': {exc}", file=sys.stderr)

        # Hint about local wheel presence for quick debugging
        wheel_dir = PROJECT_ROOT / "resources" / "spacy"
        if wheel_dir.exists():
            wheels = sorted(wheel_dir.glob(f"{model_name}-*.whl"))
            if wheels:
                print("Found wheel(s) in resources/spacy:")
                for w in wheels:
                    print(f" - {w}")
        return 1

    doc = nlp("Bonjour, ceci est un test rapide de spaCy.")
    print(f"Pipeline components: {nlp.pipe_names}")
    print("Tokens:", " | ".join([f"{t.text}/{t.pos_}" for t in doc]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
