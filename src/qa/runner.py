"""Runs the QA corpus through the correction engine and reports the section H metrics.

This is the baseline instrument. Every later change to the guardrails or the improvers is
measured against a run of this, so the output is deliberately stable and comparable: a fixed
corpus seed, raw LanguageTool counts, and a JSON report that diffs cleanly.

Needs a running LanguageTool server. Usage:

    python -m src.qa.runner --json build/qa/report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.qa import metrics
from src.qa.corpus import (
    TAG_INCOMPLETE,
    TAG_MIXED_ACRONYMS,
    TAG_NO_ENTITIES,
    TAG_NUMBERS_DATES,
    TAG_PROPER_NOUNS,
    TAG_SHORT_SENTENCES,
    CorpusItem,
    corpus_summary,
    generate_corpus,
)

#: H4's target. The engine is not expected to meet this until the guardrail work lands;
#: the runner reports the gap rather than hiding it.
TARGET_ERROR_REDUCTION = 0.80

#: H5's bound for the default "Équilibré" behaviour.
MAX_MEAN_SENTENCE_WORDS = 35.0


@dataclass
class ItemResult:
    id: str
    tags: list[str]
    errors_before: int
    errors_after: int
    error_reduction: float
    illegal_additions: dict
    mean_sentence_words_before: float
    mean_sentence_words_after: float
    syllables_per_sentence_before: float
    syllables_per_sentence_after: float
    unchanged: bool
    violations: list[str] = field(default_factory=list)
    errored: str = ""
    corrected: str = ""


@dataclass
class CorpusReport:
    corpus: dict
    items: list[ItemResult]
    aggregate: dict

    def passed(self) -> bool:
        return self.aggregate["illegal_additions_total"] == 0 and not self.aggregate["violations"]


def _check_adversarial(item: CorpusItem, corrected: str, illegal: dict) -> list[str]:
    """Assert the rules a given text exists to test. Returns violation descriptions."""
    violations: list[str] = []

    if TAG_NO_ENTITIES in item.tags and corrected.strip() != item.errored.strip():
        violations.append("H8: a clean text with no entities was modified")

    if TAG_INCOMPLETE in item.tags and ".." not in corrected:
        violations.append("B1: the deliberate blank was filled in")

    if TAG_MIXED_ACRONYMS in item.tags:
        for token in ("CAF", "SMS", "https://www.service-public.fr/particuliers"):
            if token not in corrected:
                violations.append(f"H11: '{token}' was altered")

    if TAG_PROPER_NOUNS in item.tags and illegal["entities"]:
        violations.append(f"H9: entities appeared that were not in the input: {illegal['entities']}")

    if TAG_NUMBERS_DATES in item.tags and illegal["numbers_and_dates"]:
        violations.append(f"A3: numbers or dates appeared: {illegal['numbers_and_dates']}")

    if TAG_SHORT_SENTENCES in item.tags:
        before = metrics.mean_sentence_length(item.errored)
        after = metrics.mean_sentence_length(corrected)
        if after > before + 1.0:
            violations.append(f"H10: short sentences were lengthened ({before:.1f} -> {after:.1f})")

    if illegal["total"] and not violations:
        violations.append(f"H3: illegal additions: {illegal}")

    return violations


def run_corpus(improver, lt_client, nlp, items: list[CorpusItem], *, keep_text: bool = False) -> CorpusReport:
    results: list[ItemResult] = []

    for item in items:
        corrected = improver.improve(item.errored)

        errors_before = metrics.count_lt_errors(item.errored, lt_client)
        errors_after = metrics.count_lt_errors(corrected, lt_client)
        illegal = metrics.illegal_additions(item.errored, corrected, nlp)

        before_readability = metrics.readability(item.errored)
        after_readability = metrics.readability(corrected)

        results.append(
            ItemResult(
                id=item.id,
                tags=list(item.tags),
                errors_before=errors_before,
                errors_after=errors_after,
                error_reduction=metrics.error_reduction(errors_before, errors_after),
                illegal_additions=illegal,
                mean_sentence_words_before=before_readability.words_per_sentence,
                mean_sentence_words_after=after_readability.words_per_sentence,
                syllables_per_sentence_before=before_readability.syllables_per_sentence,
                syllables_per_sentence_after=after_readability.syllables_per_sentence,
                unchanged=corrected.strip() == item.errored.strip(),
                violations=_check_adversarial(item, corrected, illegal),
                errored=item.errored if keep_text else "",
                corrected=corrected if keep_text else "",
            )
        )

    total_before = sum(r.errors_before for r in results)
    total_after = sum(r.errors_after for r in results)
    all_violations = [f"{r.id}: {v}" for r in results for v in r.violations]

    aggregate = {
        # H4, computed over the corpus as a whole rather than as a mean of ratios, so
        # texts with many errors are not outweighed by texts with one.
        "error_reduction_overall": metrics.error_reduction(total_before, total_after),
        "error_reduction_target": TARGET_ERROR_REDUCTION,
        "errors_before": total_before,
        "errors_after": total_after,
        # H3
        "illegal_additions_total": sum(r.illegal_additions["total"] for r in results),
        # H5
        "mean_sentence_words_after": (
            sum(r.mean_sentence_words_after for r in results) / len(results) if results else 0.0
        ),
        "mean_sentence_words_bound": MAX_MEAN_SENTENCE_WORDS,
        # H6
        "syllables_per_sentence_before": (
            sum(r.syllables_per_sentence_before for r in results) / len(results) if results else 0.0
        ),
        "syllables_per_sentence_after": (
            sum(r.syllables_per_sentence_after for r in results) / len(results) if results else 0.0
        ),
        "texts_left_unchanged": sum(1 for r in results if r.unchanged),
        "violations": all_violations,
    }

    return CorpusReport(corpus=corpus_summary(items), items=results, aggregate=aggregate)


def format_report(report: CorpusReport) -> str:
    aggregate = report.aggregate
    lines = [
        "DYS-fr QA corpus report",
        "=" * 60,
        f"texts               {report.corpus['texts']}",
        f"injected errors     {report.corpus['injected_errors']} {report.corpus['by_category']}",
        "",
        "H3  illegal additions      "
        f"{aggregate['illegal_additions_total']}  (target 0)",
        "H4  error reduction        "
        f"{aggregate['error_reduction_overall']:.1%}  (target {aggregate['error_reduction_target']:.0%})"
        f"   [{aggregate['errors_before']} -> {aggregate['errors_after']}]",
        "H5  mean sentence words    "
        f"{aggregate['mean_sentence_words_after']:.1f}  (bound {aggregate['mean_sentence_words_bound']:.0f})",
        "H6  syllables/sentence     "
        f"{aggregate['syllables_per_sentence_before']:.1f} -> {aggregate['syllables_per_sentence_after']:.1f}",
        "",
        f"texts left unchanged     {aggregate['texts_left_unchanged']} / {report.corpus['texts']}",
    ]

    if aggregate["violations"]:
        lines.append("")
        lines.append(f"ADVERSARIAL VIOLATIONS ({len(aggregate['violations'])})")
        lines.extend(f"  - {violation}" for violation in aggregate["violations"])
    else:
        lines.append("adversarial checks       all passed")

    return "\n".join(lines)


def build_engine(cfg):
    """Construct the light-mode improver directly, bypassing the Streamlit-cached factory."""
    import os

    from src.guardrails.spacy_loader import load_french_nlp
    from src.improvers.lt_client import LTClient
    from src.improvers.lt_improver import LTImprover

    lt_cfg = cfg["lt"]
    server_cfg = lt_cfg["server"]
    server_url = os.getenv(
        "LT_URL", f"http://{server_cfg['host']}:{server_cfg['port']}"
    )
    lang = os.getenv("LT_LANG", lt_cfg["lang"])

    spacy_cfg = cfg["spacy"]
    nlp = load_french_nlp(
        spacy_cfg["model"],
        target_dir=spacy_cfg.get("target_dir"),
        only_ner_pos=spacy_cfg.get("only_ner_pos", True),
        add_date_ruler=spacy_cfg.get("add_date_ruler", False),
    )

    return LTImprover(lang=lang, server_url=server_url, nlp=nlp), LTClient(lang, server_url), nlp


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=None, help="Corpus seed (default: fixed).")
    parser.add_argument("--json", type=Path, default=None, help="Write the full report as JSON.")
    parser.add_argument("--keep-text", action="store_true", help="Include texts in the JSON.")
    args = parser.parse_args()

    from src.utils.config import load_config

    cfg = load_config()
    items = generate_corpus(**({"seed": args.seed} if args.seed is not None else {}))

    try:
        improver, lt_client, nlp = build_engine(cfg)
    except Exception as exc:  # noqa: BLE001 - the message matters more than the type
        print(f"Could not build the engine: {exc}", file=sys.stderr)
        print("Is the LanguageTool server running? python scripts/start_lt_server.py", file=sys.stderr)
        return 2

    report = run_corpus(improver, lt_client, nlp, items, keep_text=args.keep_text)
    print(format_report(report))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {"corpus": report.corpus, "aggregate": report.aggregate,
                 "items": [asdict(item) for item in report.items]},
                indent=2, ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"\nreport written to {args.json}")

    return 0 if report.passed() else 1


if __name__ == "__main__":
    raise SystemExit(main())
