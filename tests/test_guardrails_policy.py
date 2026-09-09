"""Tests for the no-additions policy layer.

This is the product's central promise — never add information the user did not write — so
the tests run against the real spaCy pipeline rather than fakes. A fake would happily agree
with whatever the code believes about part-of-speech tags and named entities, which is
exactly where this layer can be wrong.

The two failure modes matter differently and both are covered:

- **Letting an invention through** is the one the user cannot detect. Fluent text, wrong facts.
- **Rejecting a correction** is the one that makes the product useless. A first version of
  this layer rejected "supermarchet" -> "supermarché" as a 50% novelty ratio, which would
  have refused every spelling fix the tool exists to make.
"""

from __future__ import annotations

import pytest

from src.guardrails.numbers_date import (
    date_words_in,
    new_numbers_and_dates,
    number_words_in,
    numbers_in,
)
from src.guardrails.policy import (
    should_accept_correction,
    validate_no_neologisms,
    validate_no_new_entities,
    validate_no_new_numbers_dates,
    validate_no_new_propn,
    validate_novelty_ratio,
)


@pytest.fixture(scope="module")
def nlp():
    from src.guardrails.spacy_loader import load_french_nlp
    from src.utils.config import load_config

    cfg = load_config()["spacy"]
    try:
        return load_french_nlp(
            cfg["model"],
            target_dir=cfg.get("target_dir"),
            only_ner_pos=cfg.get("only_ner_pos", True),
            add_date_ruler=cfg.get("add_date_ruler", False),
        )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"French spaCy model unavailable: {exc}")


class TestNumberAndDateExtraction:
    """Pure text, no model needed."""

    def test_finds_digits_and_ordinals(self):
        found = numbers_in("Le 14 mars 2026 à 9 h 45, au 3e étage, porte 412.")
        assert "14" in found and "2026" in found and "412" in found

    def test_finds_month_names(self):
        assert date_words_in("Le rendez-vous est en mars ou en Décembre.") == ["mars", "décembre"]

    def test_finds_spelled_out_numbers(self):
        # A spell checker can turn a garbled word into one of these.
        assert "douze" in number_words_in("Nous partons le douze mai.")

    def test_identical_text_adds_nothing(self):
        text = "Il faut apporter 2 photos et 35 euros avant le 14 mars."
        assert new_numbers_and_dates(text, text) == []

    def test_detects_an_invented_figure(self):
        assert "2" in new_numbers_and_dates("Apporte des photos.", "Apporte 2 photos.")

    def test_detects_an_invented_spelled_number(self):
        assert "douze" in new_numbers_and_dates("Nous partons en mai.", "Nous partons le douze mai.")

    def test_deleting_a_number_is_not_an_addition(self):
        assert new_numbers_and_dates("Apporte 2 photos.", "Apporte des photos.") == []

    def test_correcting_a_misspelled_number_word_is_not_an_addition(self):
        # The corpus caught "kinq" being correctly fixed to "cinq" and reported as an
        # invention. Spelled-out numbers are ordinary words and get misspelled.
        assert new_numbers_and_dates(
            "Les croissants avant kinq heures.", "Les croissants avant cinq heures."
        ) == []

    def test_correcting_a_misspelled_month_is_not_an_addition(self):
        assert new_numbers_and_dates("Le douze mrs.", "Le douze mars.") == []

    def test_digits_are_compared_strictly(self):
        # "2" and "3" are one edit apart. Tolerating that would defeat the rule entirely.
        assert new_numbers_and_dates("Apporte 2 photos.", "Apporte 3 photos.") == ["3"]


class TestValidateNoNewNumbersDates:
    def test_passes_when_nothing_is_added(self):
        assert validate_no_new_numbers_dates("Il fait beau.", "Il fait beau.").passed

    def test_fails_and_says_what_appeared(self):
        result = validate_no_new_numbers_dates("Le rendez-vous est fixé.", "Le rendez-vous est le 14 mars.")
        assert not result.passed
        assert "14" in result.reason


class TestValidateNoNewEntities:
    def test_passes_on_an_unchanged_entity(self, nlp):
        text = "Camille habite à Bordeaux."
        assert validate_no_new_entities(nlp(text), nlp(text)).passed

    def test_fails_on_an_invented_place(self, nlp):
        result = validate_no_new_entities(
            nlp("Je vais au marché."), nlp("Je vais au marché à Marseille.")
        )
        assert not result.passed
        assert "Marseille" in result.reason

    def test_a_corrected_spelling_is_not_a_new_entity(self, nlp):
        # The false positive that made the first version unusable.
        assert validate_no_new_entities(
            nlp("Ils fetent Noel chez Camile."), nlp("Ils fêtent Noël chez Camille.")
        ).passed


class TestValidateNoNewPropn:
    def test_passes_when_names_are_unchanged(self, nlp):
        text = "Camille et Jonathan arrivent demain."
        assert validate_no_new_propn(nlp(text), nlp(text)).passed

    def test_fails_on_an_invented_name(self, nlp):
        result = validate_no_new_propn(
            nlp("Je pars en voyage."), nlp("Je pars en voyage avec Bertrand.")
        )
        assert not result.passed


class TestValidateNovelty:
    def test_a_spelling_fix_scores_no_novelty(self, nlp):
        # If this fails, the guardrail rejects the product's own core behaviour.
        assert validate_novelty_ratio(
            nlp("Je sui aller au supermarchet."), nlp("Je suis alle au supermarche.")
        ).passed

    def test_a_paraphrase_is_rejected(self, nlp):
        result = validate_novelty_ratio(
            nlp("Le chat dort."),
            nlp("Le petit animal se repose tranquillement sur le canape."),
        )
        assert not result.passed
        assert "novelty ratio" in result.reason

    def test_the_threshold_is_configurable(self, nlp):
        original, corrected = nlp("Le chat dort."), nlp("Le chat dort profondement.")
        assert not validate_novelty_ratio(original, corrected, threshold=0.0).passed
        assert validate_novelty_ratio(original, corrected, threshold=0.9).passed

    def test_the_default_threshold_is_the_approved_twelve_percent(self):
        from src.guardrails.novelty import DEFAULT_THRESHOLD

        assert DEFAULT_THRESHOLD == 0.12  # decision I-1


class TestValidateNoNeologisms:
    def test_passes_on_ordinary_french(self, nlp):
        text = "Le chat mange une pomme rouge."
        assert validate_no_neologisms(nlp(text), nlp(text)).passed

    def test_fails_on_an_invented_word(self, nlp):
        result = validate_no_neologisms(nlp("Il flurbait hier."), nlp("Il zorglubait hier."))
        assert not result.passed
        assert "zorglubait" in result.reason


class TestShouldAcceptCorrection:
    """The orchestrator, which is what the improvers actually call."""

    @pytest.mark.parametrize(
        "original, corrected",
        [
            ("Je sui aller au supermarchet.", "Je suis alle au supermarche."),
            ("Le ciel est gris.", "Le ciel est gris."),
            ("Ils fetent Noel demain.", "Ils fêtent Noël demain."),
            ("nous parton le douze mai.", "Nous partons le douze mai."),
        ],
    )
    def test_accepts_corrections(self, nlp, original, corrected):
        result = should_accept_correction(original, corrected, nlp)
        assert result.passed, result.reason

    @pytest.mark.parametrize(
        "original, corrected",
        [
            ("Il faut apporter des photos.", "Il faut apporter 2 photos."),
            ("Le rendez-vous est fixe.", "Le rendez-vous est fixe en mars."),
            ("Je vais au marche.", "Je vais au marche a Marseille."),
            ("Il flurbait hier.", "Il zorglubait hier."),
            ("Le chat dort.", "Le petit animal se repose tranquillement sur le canape."),
        ],
    )
    def test_rejects_inventions(self, nlp, original, corrected):
        result = should_accept_correction(original, corrected, nlp)
        assert not result.passed
        assert result.reason

    def test_an_identical_text_short_circuits(self, nlp):
        text = "Le rendez-vous est le 14 mars 2026 avec Camille."
        assert should_accept_correction(text, text, nlp).passed

    def test_the_result_is_falsy_on_failure(self, nlp):
        # The improvers rely on ValidationResult being usable as a boolean.
        assert not should_accept_correction("Il fait beau.", "Il fait beau le 14 mars.", nlp)
