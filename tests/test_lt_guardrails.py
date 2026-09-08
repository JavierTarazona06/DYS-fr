"""Unit tests for the LanguageTool replacement guards.

These are the filters that stand between a LanguageTool suggestion and the user's text, so
they are the enforcement point for the no-additions policy in light mode. Pure functions:
no server, no spaCy model.

TODO-9 and TODO-10 were both found by the QA corpus (`src/qa/`) rather than by review, and
the cases below are taken from that run.
"""

from __future__ import annotations

import pytest

from src.improvers.lt_improver import (
    _BLOCK_RULES,
    _does_not_add_digits,
    _does_not_introduce_proper_noun,
    _normalise_for_comparison,
    _safe_by_rule,
    _token_delta_ok,
)


class _Match:
    """Minimal stand-in for a language_tool_python match."""

    def __init__(self, rule_id: str | None):
        self.ruleId = rule_id


class TestBlockedRules:
    """TODO-10: a deliberate blank must survive correction."""

    def test_double_punctuation_is_blocked(self):
        # "l'indépendance des États-Unis est le .. de .." must come back incomplete (B1).
        assert _safe_by_rule(_Match("DOUBLE_PUNCTUATION")) is False

    def test_ordinary_rules_pass(self):
        assert _safe_by_rule(_Match("FR_SPELLING_RULE")) is True
        assert _safe_by_rule(_Match("UPPERCASE_SENTENCE_START")) is True

    def test_a_match_without_a_rule_id_is_not_blocked(self):
        assert _safe_by_rule(_Match(None)) is True

    def test_the_block_list_is_not_empty(self):
        # _BLOCK_CATEGORIES is inert because it is empty (TODO-3); this one must not be.
        assert _BLOCK_RULES


class TestProperNounGuard:
    """TODO-9: LanguageTool must not substitute an invented proper noun."""

    def test_blocks_the_commune_substituted_for_a_garbled_word(self):
        # The defect exactly as the corpus found it, in text t17: LanguageTool's first
        # suggestion for "duoze" is the elided "d'Eauze", whose leading letter is lowercase.
        # A guard that only inspects a token's first character walks straight past it.
        assert _does_not_introduce_proper_noun("duoze", "d'Eauze") is False
        assert _does_not_introduce_proper_noun("duoze", "Eauze") is False

    def test_blocks_an_invented_name_after_a_hyphen(self):
        assert _does_not_introduce_proper_noun("saintmachin", "Saint-Étienne") is False

    def test_allows_the_correct_suggestion_for_the_same_word(self):
        # "douze" is the right fix for "duoze" and must not be caught in the crossfire.
        assert _does_not_introduce_proper_noun("duoze", "douze") is True

    def test_blocks_any_unrelated_capitalised_word(self):
        assert _does_not_introduce_proper_noun("marchet", "Marseille") is False

    def test_allows_capitalising_a_word_the_user_already_wrote(self):
        # "paris" -> "Paris" is a correction of an existing word, not an invention.
        assert _does_not_introduce_proper_noun("paris", "Paris") is True

    def test_allows_sentence_start_capitalisation(self):
        # UPPERCASE_SENTENCE_START produces exactly this and must keep working.
        assert _does_not_introduce_proper_noun("de", "De") is True

    def test_allows_a_restored_elision(self):
        # "jai" -> "J'ai" capitalises and adds an apostrophe; normalisation collapses both.
        assert _does_not_introduce_proper_noun("jai", "J'ai") is True

    def test_allows_a_restored_accent_on_a_capitalised_word(self):
        assert _does_not_introduce_proper_noun("Noel", "Noël") is True

    def test_allows_lowercase_corrections_untouched(self):
        assert _does_not_introduce_proper_noun("supermarchet", "supermarché") is True

    def test_allows_a_multiword_replacement_whose_capital_was_present(self):
        assert _does_not_introduce_proper_noun("Nous parton", "Nous partons") is True


class TestNormalisation:
    @pytest.mark.parametrize(
        "text, expected",
        [
            ("Noël", "noel"),
            ("J'ai", "jai"),
            ("Villeneuve-sur-Lot", "villeneuvesurlot"),
            ("De", "de"),
        ],
    )
    def test_normalisation_strips_case_accents_and_punctuation(self, text, expected):
        assert _normalise_for_comparison(text) == expected


class TestExistingGuardsStillHold:
    """The guards that were already there must not regress."""

    def test_digits_cannot_be_introduced(self):
        assert _does_not_add_digits("deux", "2") is False
        assert _does_not_add_digits("2 photos", "2 photo") is True

    def test_token_delta_is_bounded(self):
        assert _token_delta_ok("fiat", "est fiat", 1) is True   # currently permitted
        assert _token_delta_ok("fiat", "il est fiat", 1) is False
