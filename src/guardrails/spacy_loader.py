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
    candidates: list[Path] = []

    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "DYS-fr" / "spacy-cache")

    candidates.append(Path(tempfile.gettempdir()) / "dys-fr-spacy-cache")
    candidates.append(Path.home() / ".cache" / "dys-fr" / "spacy-cache")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except Exception:
            continue

    raise PermissionError("Could not create a writable cache directory for spaCy model extraction.")


def _extract_model_from_wheel(model_name: str, target_dir: Path) -> Path:
    wheels = sorted(target_dir.glob(f"{model_name}-*.whl"))
    if not wheels:
        raise FileNotFoundError(f"No wheel found for model '{model_name}' in {target_dir}")

    wheel_path = wheels[-1]
    extract_root = _get_model_cache_root() / wheel_path.stem
    marker = extract_root / ".extracted.ok"

    if not marker.exists():
        extract_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(wheel_path, "r") as archive:
            archive.extractall(extract_root)
        marker.write_text("ok", encoding="utf-8")

    package_root = extract_root / model_name
    if not package_root.exists():
        raise FileNotFoundError(f"Could not find extracted package root for '{model_name}' in {extract_root}")

    candidates = sorted(
        path
        for path in package_root.glob(f"{model_name}-*")
        if path.is_dir() and (path / "config.cfg").exists()
    )
    if not candidates:
        raise FileNotFoundError(f"Could not locate extracted model data for '{model_name}' in {package_root}")

    return candidates[-1]


def _resolve_extracted_model_dir(model_name: str, target_dir: Path) -> Path | None:
    extracted_dir = target_dir / "models" / model_name
    if (extracted_dir / "config.cfg").exists():
        return extracted_dir
    return None


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
    :param only_ner_pos: If True, disables heavy components (parser); keeps NER/POS/lemmatizer.
    :param add_date_ruler: If True, injects a rule-based DATE recognizer before the NER.
    :return: Language object ready to process French text.
    """
    disable = ()
    if only_ner_pos:
        # Keep senter if you need sentence boundaries without the parser
        disable = ("parser",)
    model_name = str(model)

    try:
        nlp = spacy.load(model_name, disable=disable)
    except OSError:
        path_model = Path(model_name)
        if path_model.exists():
            nlp = spacy.load(path_model, disable=disable)  # type: ignore[arg-type]
        else:
            resolved_target_dir = (
                resolve_runtime_path("resources", "spacy")
                if target_dir is None
                else (Path(target_dir) if Path(target_dir).is_absolute() else resolve_runtime_path(target_dir))
            )

            extracted_dir = _resolve_extracted_model_dir(model_name, resolved_target_dir)
            if extracted_dir is not None:
                nlp = spacy.load(extracted_dir, disable=disable)  # type: ignore[arg-type]
            else:
                extracted_model_dir = _extract_model_from_wheel(model_name, resolved_target_dir)
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
