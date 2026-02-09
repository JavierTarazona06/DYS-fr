from __future__ import annotations
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

import spacy
from spacy.language import Language
from spacy.pipeline import EntityRuler

from src.utils.paths import resolve_runtime_path

DATE_RULER_NAME = "guardrails_date_ruler"
MONTH_NAMES: tuple[str, ...] = (
    "janvier",
    "février",
    "fevrier",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "aout",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
    "decembre",
)
DATE_REGEX_PATTERNS: tuple[str, ...] = (
    r"^\d{1,2}/\d{1,2}/\d{2,4}$",
    r"^\d{1,2}-\d{1,2}-\d{2,4}$",
    r"^\d{1,2}\.\d{1,2}\.\d{2,4}$",
    r"^\d{4}-\d{1,2}-\d{1,2}$",
    r"^\d{1,2}/\d{4}$",
)


def ensure_date_ruler(nlp: Language, *, months: Iterable[str] = MONTH_NAMES) -> None:
    """Add a lightweight EntityRuler that tags common French date formats."""
    if DATE_RULER_NAME in nlp.pipe_names:
        return

    ruler: EntityRuler = nlp.add_pipe("entity_ruler", name=DATE_RULER_NAME, before="ner")

    prefix = {"LOWER": {"IN": ["le", "la", "les"]}, "OP": "?"}
    day_token = {"TEXT": {"REGEX": r"^\d{1,2}$"}}
    month_token = {"LOWER": {"IN": list(months)}}
    year_token = {"TEXT": {"REGEX": r"^\d{2,4}$"}, "OP": "?"}

    patterns = [
        {"label": "DATE", "pattern": [prefix, day_token, month_token, year_token]},
        {"label": "DATE", "pattern": [prefix, month_token, day_token, year_token]},
        {"label": "DATE", "pattern": [month_token, day_token, year_token]},
        {"label": "DATE", "pattern": [day_token, month_token]},
        {"label": "DATE", "pattern": [month_token, year_token]},
    ]

    for regex in DATE_REGEX_PATTERNS:
        patterns.append({"label": "DATE", "pattern": [{"TEXT": {"REGEX": regex}}]})

    ruler.add_patterns(patterns)


def _get_model_cache_root() -> Path:
    """Return a writable cache location for extracted spaCy models."""
    candidates: list[Path] = []

    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "DYS-fr" / "spacy_models")

    candidates.append(Path(tempfile.gettempdir()) / "dys-fr-spacy-models")
    candidates.append(Path.home() / ".cache" / "dys-fr" / "spacy_models")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except Exception:
            continue

    raise PermissionError(
        "Could not find a writable cache directory to extract spaCy model wheels."
    )


def _extract_model_from_wheel(model_name: str, target_dir: Path) -> Path:
    """
    Extract a spaCy model wheel into a local cache and return the model directory path.

    The expected wheel naming convention is `<model_name>-*.whl`.
    """
    wheels = sorted(target_dir.glob(f"{model_name}-*.whl"))
    if not wheels:
        raise FileNotFoundError(
            f"No wheel found for model '{model_name}' in: {target_dir}"
        )

    wheel_path = wheels[-1]
    cache_root = _get_model_cache_root()
    extract_root = cache_root / wheel_path.stem
    marker = extract_root / ".extracted.ok"

    if not marker.exists():
        extract_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(wheel_path, "r") as archive:
            archive.extractall(extract_root)
        marker.write_text("ok", encoding="utf-8")

    pkg_root = extract_root / model_name
    if not pkg_root.exists():
        raise FileNotFoundError(
            f"Extracted wheel does not contain package folder: {pkg_root}"
        )

    candidates = sorted(
        p for p in pkg_root.glob(f"{model_name}-*") if p.is_dir() and (p / "config.cfg").exists()
    )
    if not candidates:
        raise FileNotFoundError(
            f"Could not find extracted model directory with config.cfg under: {pkg_root}"
        )
    return candidates[-1]


def load_french_nlp(
    model: str | Path,
    *,
    target_dir: str | Path | None = None,
    only_ner_pos: bool = True,
    add_date_ruler: bool = True,
) -> Language:
    """
    Load spaCy FR with a lightweight configuration for guardrails.

    :param model: Package name ('fr_core_news_md') or path to the model directory.
    :param target_dir: Optional directory containing spaCy model wheel(s) for offline fallback.
    :param only_ner_pos: If True, disables heavy components (parser); keeps NER/POS/lemmatizer.
    :param add_date_ruler: If True, injects a rule-based DATE recognizer before the NER.
    :return: Language object ready to process French text.
    """
    disable = ()
    if only_ner_pos:
        # Keep senter if you need sentence boundaries without the parser
        disable = ("parser",)

    model_name = str(model)

    # 1) Preferred: installed package name.
    try:
        nlp = spacy.load(model_name, disable=disable)
    except OSError:
        # 2) Path-based fallback: model argument as a directory.
        path_model = Path(model_name)
        if path_model.exists():
            nlp = spacy.load(path_model, disable=disable)  # type: ignore[arg-type]
        else:
            # 3) Offline fallback from wheel stored in resources/spacy.
            target = (
                resolve_runtime_path(target_dir)
                if target_dir is not None
                else resolve_runtime_path("resources/spacy")
            )
            extracted_model_dir = _extract_model_from_wheel(model_name, Path(target))
            nlp = spacy.load(extracted_model_dir, disable=disable)  # type: ignore[arg-type]
    # If you disabled the parser and need sentences, ensure senter is available
    if only_ner_pos:
        if "senter" in nlp.component_names:
            if "senter" not in nlp.pipe_names:
                nlp.enable_pipe("senter")
        else:
            nlp.add_pipe("senter")

    if add_date_ruler:
        ensure_date_ruler(nlp)

    return nlp
