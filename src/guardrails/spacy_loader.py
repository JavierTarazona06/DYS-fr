from __future__ import annotations
from pathlib import Path
from typing import Iterable

import spacy
from spacy.language import Language
from spacy.pipeline import EntityRuler

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


def load_french_nlp(
    model: str | Path,
    *,
    only_ner_pos: bool = True,
    add_date_ruler: bool = False,
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
    try:
        nlp = spacy.load(str(model), disable=disable)
    except OSError:
        # Load by path (e.g., resources/spacy/fr_core_news_md/)
        nlp = spacy.load(Path(model), disable=disable)  # type: ignore[arg-type]
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