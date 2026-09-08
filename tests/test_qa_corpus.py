"""Tests for the QA corpus and its error injectors.

The corpus is the ground truth every metric is computed against, so it has to be
reproducible and its labels have to be honest. No LanguageTool server or spaCy model needed.
"""

from __future__ import annotations

import random

import pytest

from src.qa.corpus import (
    BASE_TEXTS,
    TAG_INCOMPLETE,
    TAG_MIXED_ACRONYMS,
    TAG_NO_ENTITIES,
    TAG_NO_INJECTION,
    TAG_NUMBERS_DATES,
    TAG_PROPER_NOUNS,
    TAG_SHORT_SENTENCES,
    corpus_summary,
    generate_corpus,
)
from src.qa.error_taxonomy import INJECTORS, ErrorCategory


class TestCorpusShape:
    def test_has_thirty_texts_as_decided_in_I10(self):
        assert len(BASE_TEXTS) == 30
        assert len(generate_corpus()) == 30

    def test_text_ids_are_unique(self):
        ids = [item.id for item in generate_corpus()]
        assert len(set(ids)) == len(ids)

    def test_every_text_is_multi_sentence(self):
        # H5 measures mean sentence length, which single sentences cannot express.
        for base in BASE_TEXTS:
            assert base.text.count(".") + base.text.count("!") + base.text.count("?") >= 2, base.id


class TestDeterminism:
    def test_same_seed_produces_an_identical_corpus(self):
        first = generate_corpus(seed=123)
        second = generate_corpus(seed=123)
        assert [item.errored for item in first] == [item.errored for item in second]

    def test_different_seeds_produce_different_errors(self):
        assert generate_corpus(seed=1)[0].errored != generate_corpus(seed=2)[0].errored

    def test_one_text_changing_does_not_shift_the_others(self):
        """Per-text seeding: editing one base text must not churn the whole corpus."""
        corpus = {item.id: item.errored for item in generate_corpus()}
        again = {item.id: item.errored for item in generate_corpus()}
        assert corpus == again


class TestGroundTruth:
    def test_injected_texts_actually_differ_from_the_clean_version(self):
        for item in generate_corpus():
            if TAG_NO_INJECTION in item.tags:
                continue
            assert item.errored != item.clean, item.id

    def test_every_injected_error_is_recorded(self):
        for item in generate_corpus():
            if TAG_NO_INJECTION in item.tags:
                assert item.injected == ()
            else:
                assert item.injected, item.id

    def test_each_recorded_error_names_a_real_transformation(self):
        for item in generate_corpus():
            for error in item.injected:
                assert error.original != error.replacement, f"{item.id}/{error.injector_id}"
                assert error.injector_id in {inj.id for inj in INJECTORS}

    def test_clean_texts_are_left_verbatim(self):
        for item in generate_corpus():
            if TAG_NO_INJECTION in item.tags:
                assert item.errored == item.clean, item.id


class TestAdversarialCoverage:
    """Each tag corresponds to a rule in docs/business-rules.md that must be testable."""

    @pytest.mark.parametrize(
        "tag",
        [
            TAG_NO_ENTITIES,
            TAG_PROPER_NOUNS,
            TAG_SHORT_SENTENCES,
            TAG_MIXED_ACRONYMS,
            TAG_INCOMPLETE,
            TAG_NUMBERS_DATES,
        ],
    )
    def test_tag_is_present_in_the_corpus(self, tag):
        assert any(tag in item.tags for item in generate_corpus()), tag

    def test_the_incomplete_text_really_is_incomplete(self):
        item = next(i for i in generate_corpus() if TAG_INCOMPLETE in i.tags)
        assert ".." in item.errored

    def test_the_acronym_text_carries_a_url_and_an_acronym(self):
        item = next(i for i in generate_corpus() if TAG_MIXED_ACRONYMS in i.tags)
        assert "https://" in item.errored
        assert "CAF" in item.errored

    def test_the_short_sentence_text_has_sentences_under_seven_words(self):
        item = next(i for i in generate_corpus() if TAG_SHORT_SENTENCES in i.tags)
        lengths = [len(part.split()) for part in item.errored.split(".") if part.strip()]
        assert all(length <= 6 for length in lengths), lengths


class TestTaxonomyCoverage:
    def test_all_three_categories_are_represented(self):
        summary = corpus_summary(generate_corpus())
        for category in ErrorCategory:
            assert summary["by_category"][category.value] > 0, category

    def test_every_injector_finds_a_candidate_somewhere_in_the_corpus(self):
        """An injector that never fires is dead weight pretending to be coverage."""
        fired = {error.injector_id for item in generate_corpus() for error in item.injected}
        never_fired = {inj.id for inj in INJECTORS} - fired
        assert not never_fired, f"injectors that never fire: {sorted(never_fired)}"

    def test_injectors_are_deterministic_given_the_same_rng(self):
        text = "Je suis allé au supermarché pour acheter du pain et du lait."
        for injector in INJECTORS:
            first, _ = injector.apply(text, random.Random(7))
            second, _ = injector.apply(text, random.Random(7))
            assert first == second, injector.id

    def test_an_injector_with_no_candidate_returns_the_text_untouched(self):
        text = "aaa bbb ccc"
        for injector in INJECTORS:
            result, error = injector.apply(text, random.Random(1))
            if error is None:
                assert result == text, injector.id
