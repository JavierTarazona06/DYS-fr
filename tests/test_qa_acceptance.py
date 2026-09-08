"""Acceptance gate: runs the QA corpus through the real engine and checks section H.

Needs a running LanguageTool server and the spaCy model; skips cleanly without them, so it
does not break a machine that only wants the fast unit tests.

    python scripts/start_lt_server.py      # in another terminal
    pytest tests/test_qa_acceptance.py -v

The H3 test is an expected failure today, and deliberately so: the run that established
this baseline found two genuine defects, recorded as TODO-9 and TODO-10. When phase 2 fixes
them the test will XPASS strictly and demand to be turned into a plain assertion.
"""

from __future__ import annotations

import pytest
import requests

from src.qa.corpus import generate_corpus
from src.qa.runner import TARGET_ERROR_REDUCTION, build_engine, run_corpus
from src.utils.config import load_config


def _lt_reachable(cfg) -> bool:
    server = cfg["lt"]["server"]
    try:
        response = requests.get(
            f"http://{server['host']}:{server['port']}/v2/languages", timeout=2
        )
        return response.status_code == 200
    except requests.RequestException:
        return False


@pytest.fixture(scope="module")
def report():
    cfg = load_config()
    if not _lt_reachable(cfg):
        pytest.skip("LanguageTool server is not running (python scripts/start_lt_server.py)")

    improver, lt_client, nlp = build_engine(cfg)
    return run_corpus(improver, lt_client, nlp, generate_corpus())


def test_the_corpus_is_the_expected_size(report):
    assert report.corpus["texts"] == 30
    assert report.corpus["injected_errors"] > 0


def test_h4_error_reduction_meets_the_target(report):
    """At least 80% of LanguageTool errors removed, over the corpus as a whole."""
    achieved = report.aggregate["error_reduction_overall"]
    assert achieved >= TARGET_ERROR_REDUCTION, (
        f"error reduction {achieved:.1%} is below the {TARGET_ERROR_REDUCTION:.0%} target "
        f"({report.aggregate['errors_before']} -> {report.aggregate['errors_after']})"
    )


def test_h5_mean_sentence_length_stays_within_bound(report):
    achieved = report.aggregate["mean_sentence_words_after"]
    bound = report.aggregate["mean_sentence_words_bound"]
    assert achieved <= bound, f"mean sentence length {achieved:.1f} exceeds {bound:.0f} words"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TODO-9: LanguageTool substitutes a proper noun for a garbled word. "
        "TODO-10: LanguageTool collapses a deliberate '..' blank. "
        "Both are fixed in phase 2; remove this marker then."
    ),
)
def test_h3_no_illegal_additions(report):
    """The product's central promise: never add information that was not in the input."""
    total = report.aggregate["illegal_additions_total"]
    assert total == 0, f"{total} illegal additions: {report.aggregate['violations']}"


@pytest.mark.xfail(
    strict=True,
    reason="Same two defects as H3, seen through the adversarial texts. Fixed in phase 2.",
)
def test_adversarial_texts_hold(report):
    violations = report.aggregate["violations"]
    assert not violations, "\n".join(violations)
