"""Tests for the QA metrics.

These are the numbers that decide whether DYS-fr is "fit for end users", so they need to be
right before anything is measured with them. Everything here is pure: no LanguageTool
server, no spaCy model.
"""

from __future__ import annotations

import pytest

from src.qa.metrics import (
    count_syllables,
    count_words,
    error_reduction,
    illegal_additions,
    mean_sentence_length,
    new_numbers_and_dates,
    readability,
    split_sentences,
)


class TestSentenceSplitting:
    def test_splits_on_terminal_punctuation(self):
        text = "Le chat dort. Il fait chaud ! Où vas-tu ?"
        assert split_sentences(text) == ["Le chat dort.", "Il fait chaud !", "Où vas-tu ?"]

    def test_does_not_split_on_french_abbreviations(self):
        text = "M. Dupont est arrivé. Il attend dehors."
        assert len(split_sentences(text)) == 2

    def test_does_not_split_inside_a_url(self):
        text = "Le formulaire est sur https://www.service-public.fr/particuliers. Merci."
        sentences = split_sentences(text)
        assert len(sentences) == 2
        assert "https://www.service-public.fr/particuliers." in sentences[0]

    def test_empty_text_yields_no_sentences(self):
        assert split_sentences("") == []


class TestCounting:
    def test_counts_elided_and_hyphenated_forms_as_single_words(self):
        # Orthographic words, the convention French readability work uses and the one the
        # 30-35 word bound in H5 is expressed in: "L'entraîneur" and "d'y" are one token
        # each, not article-plus-noun.
        assert count_words("L'entraîneur nous a dit d'y aller") == 6
        assert count_words("Villeneuve-sur-Lot") == 1

    @pytest.mark.parametrize(
        "word, expected",
        [
            ("chat", 1),
            ("maison", 2),
            ("supermarché", 4),
            ("a", 1),
        ],
    )
    def test_counts_syllables_by_vowel_group(self, word, expected):
        assert count_syllables(word) == expected

    def test_silent_final_e_is_not_counted(self):
        # "porte" is two vowel groups but one is the silent ending.
        assert count_syllables("porte") == 1

    def test_a_word_always_has_at_least_one_syllable(self):
        assert count_syllables("le") == 1


class TestSentenceLength:
    def test_mean_sentence_length(self):
        text = "Le chat dort. Il fait très chaud dehors."
        # 3 words + 5 words over 2 sentences
        assert mean_sentence_length(text) == 4.0

    def test_empty_text_is_zero_not_a_crash(self):
        assert mean_sentence_length("") == 0.0


class TestReadability:
    def test_shorter_sentences_score_lower(self):
        long_text = "Je suis allé au supermarché pour acheter du pain et du lait parce que le réfrigérateur était complètement vide depuis hier soir."
        short_text = "Je suis allé au supermarché. J'ai acheté du pain. Le réfrigérateur était vide."
        assert readability(short_text).words_per_sentence < readability(long_text).words_per_sentence
        assert readability(short_text).syllables_per_sentence < readability(long_text).syllables_per_sentence

    def test_empty_text_is_zero(self):
        score = readability("")
        assert score.characters_per_sentence == 0.0


class TestIllegalAdditions:
    """H3 must be exactly 0%, so these are the tests that guard the product's core promise."""

    def test_identical_text_adds_nothing(self):
        text = "Le rendez-vous est fixé au 14 mars 2026 à 9 h 45."
        assert new_numbers_and_dates(text, text) == []

    def test_detects_an_invented_number(self):
        original = "Il faut apporter deux photos."
        corrected = "Il faut apporter 2 photos et 35 euros."
        added = new_numbers_and_dates(original, corrected)
        assert "2" in added and "35" in added

    def test_detects_an_invented_month(self):
        original = "Le rendez-vous est fixé."
        corrected = "Le rendez-vous est fixé en mars."
        assert "mars" in new_numbers_and_dates(original, corrected)

    def test_removing_a_number_is_not_an_addition(self):
        # Deletion is a different rule; H3 only counts additions.
        original = "Il faut apporter 2 photos et 35 euros."
        corrected = "Il faut apporter des photos."
        assert new_numbers_and_dates(original, corrected) == []

    def test_repeating_an_existing_number_counts_as_an_addition(self):
        original = "Il faut apporter 35 euros."
        corrected = "Il faut apporter 35 euros, exactement 35 euros."
        assert new_numbers_and_dates(original, corrected) == ["35"]

    def test_entity_check_is_reported_as_skipped_without_spacy(self):
        result = illegal_additions("Camille arrive.", "Camille arrive.", nlp=None)
        assert result["entities_checked"] is False
        assert result["total"] == 0


class TestEntityResemblance:
    """The matching that stops a *corrected* entity from being reported as an invented one.

    Without this, the metric fires exactly when the engine does its job, and nobody trusts
    it. These cases are drawn from the first real corpus run.
    """

    @staticmethod
    def _resembles(entity: str, original: str) -> bool:
        import re

        from src.qa.metrics import _normalise, _resembles_input

        normalised = _normalise(original)
        tokens = re.findall(r"\b[\w-]+\b", normalised)
        return _resembles_input(entity, tokens, normalised)

    def test_a_restored_accent_is_not_an_invention(self):
        # "Noel" -> "Noël" is the engine correcting, not inventing.
        assert self._resembles("Noël", "Ils se retrouvent a Noel chez leur tante.")

    def test_a_fixed_verb_ending_is_not_an_invention(self):
        assert self._resembles("Avons", "Nous l'avon mangée hier.")

    def test_an_unrelated_proper_noun_is_an_invention(self):
        # The real defect found in the baseline run: "duoze" became the commune "Eauze".
        assert not self._resembles("Eauze", "Nous partons le duoze mai avec deux classes.")

    def test_a_wholly_new_name_is_an_invention(self):
        assert not self._resembles("Marseille", "Je suis allé au marché ce matin.")

    def test_an_exact_match_resembles(self):
        assert self._resembles("Camille", "Camille arrive demain.")


class TestBoundedEditDistance:
    @pytest.mark.parametrize(
        "a, b, limit, expected",
        [
            ("avons", "avon", 1, True),
            ("noel", "noel", 1, True),
            # Three substitutions apart, which is why "Eauze" reads as invented rather
            # than as a correction of "duoze".
            ("eauze", "duoze", 1, False),
            ("eauze", "duoze", 2, False),
            ("eauze", "duoze", 3, True),
            ("chat", "chien", 1, False),
            ("court", "beaucoup plus long", 2, False),
        ],
    )
    def test_distance_bound(self, a, b, limit, expected):
        from src.utils.text import within_edit_distance

        assert within_edit_distance(a, b, limit) is expected


class TestErrorReduction:
    """H4 asks for at least an 80% drop."""

    def test_all_errors_fixed_is_full_reduction(self):
        assert error_reduction(10, 0) == 1.0

    def test_eighty_percent_threshold(self):
        assert error_reduction(10, 2) == pytest.approx(0.8)

    def test_no_change_is_zero(self):
        assert error_reduction(10, 10) == 0.0

    def test_a_worse_result_clamps_to_zero_rather_than_going_negative(self):
        assert error_reduction(10, 25) == 0.0

    def test_a_clean_input_cannot_be_improved_and_scores_one(self):
        # Otherwise adversarial clean texts would drag the corpus average down.
        assert error_reduction(0, 0) == 1.0
