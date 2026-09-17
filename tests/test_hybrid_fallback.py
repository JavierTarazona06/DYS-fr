"""TODO-6: when the LLM pass cannot be used, hybrid mode returns light mode's correction.

It used to return the user's input. That discarded corrections light mode would have made,
and the final gate refuses a large share of LLM outputs — 15 of 39 when measured on
2026-09-17 — so hybrid mode often handed back less than light mode.

Wiring only: no model, no LanguageTool server, no spaCy. The engine paths themselves are
covered by tests/test_llm_mistral.py and the QA corpus.
"""

from __future__ import annotations

import pytest

import src.improvers.llm_improver as llm_module
import src.improvers.ollama_improver as ollama_module
from src.guardrails.policy import ValidationResult
from src.improvers.llm_improver import LLMImprover
from src.improvers.lt_improver import LTImprover
from src.improvers.ollama_improver import OllamaImprover

TEXT = "Je sui aller au magasin."
LLM_OUTPUT = "Je suis au magasin."
LIGHT_OUTPUT = "Je suis allé au magasin."


class _Match:
    message = "erreur"
    context = TEXT
    offset = 0
    errorLength = 2
    replacements = ["Je"]


class _FakeClient:
    """Reports `errors[text]` matches for a text, and a default count otherwise."""

    def __init__(self, errors: dict[str, int] | None = None, default: int = 2):
        self.errors = errors or {}
        self.default = default
        self.closed = False

    def check(self, text):
        return [_Match() for _ in range(self.errors.get(text, self.default))]

    def close(self):
        self.closed = True


class _FakeLight:
    def improve(self, text):
        assert text == TEXT, "the fallback must correct what the user wrote, not the masked text"
        return LIGHT_OUTPUT


def _gate(passed: bool):
    return lambda original, corrected, nlp, **kwargs: ValidationResult(passed, None if passed else "refused")


@pytest.fixture(autouse=True)
def no_masking(monkeypatch):
    monkeypatch.setattr(llm_module, "mask_entities", lambda doc: (TEXT, []))
    monkeypatch.setattr(ollama_module, "mask_entities", lambda doc: (TEXT, []))


def _mistral(client, llm):
    improver = object.__new__(LLMImprover)
    improver.nlp = lambda text: text  # anything non-None, so the gate runs
    improver.lt_client = client
    improver._owns_lt_client = False
    improver._light = _FakeLight()
    improver.max_tokens = 512
    improver.temperature = 0.1
    improver.llm = llm
    return improver


def _llm_returning(output):
    return lambda prompt, **kwargs: {"choices": [{"text": output, "finish_reason": "stop"}]}


def _llm_raising(prompt, **kwargs):
    raise RuntimeError("model crashed")


class TestMistralFallback:
    def test_gate_refusal_returns_light_mode_correction(self, monkeypatch):
        monkeypatch.setattr(llm_module, "should_accept_correction", _gate(False))
        improver = _mistral(_FakeClient(default=1), _llm_returning(LLM_OUTPUT))
        assert improver.improve(TEXT) == LIGHT_OUTPUT

    def test_degradation_returns_light_mode_correction(self, monkeypatch):
        monkeypatch.setattr(llm_module, "should_accept_correction", _gate(True))
        client = _FakeClient(errors={TEXT: 1, LLM_OUTPUT: 5})
        assert _mistral(client, _llm_returning(LLM_OUTPUT)).improve(TEXT) == LIGHT_OUTPUT

    def test_model_error_returns_light_mode_correction(self, monkeypatch):
        monkeypatch.setattr(llm_module, "should_accept_correction", _gate(True))
        assert _mistral(_FakeClient(), _llm_raising).improve(TEXT) == LIGHT_OUTPUT

    def test_an_accepted_output_is_returned_as_is(self, monkeypatch):
        monkeypatch.setattr(llm_module, "should_accept_correction", _gate(True))
        client = _FakeClient(errors={TEXT: 2, LLM_OUTPUT: 0})
        assert _mistral(client, _llm_returning(LLM_OUTPUT)).improve(TEXT) == LLM_OUTPUT


def _gemma(client):
    improver = object.__new__(OllamaImprover)
    improver.model_name = "gemma3:4b"
    improver.nlp = lambda text: text
    improver.lt_client = client
    improver._light = _FakeLight()
    improver.temperature = 0.1
    return improver


def _chat_returning(output):
    return lambda **kwargs: {"message": {"content": output}}


def _chat_raising(**kwargs):
    raise ConnectionError("Ollama is not running")


class TestOllamaFallback:
    def test_gate_refusal_returns_light_mode_correction(self, monkeypatch):
        monkeypatch.setattr(ollama_module, "should_accept_correction", _gate(False))
        monkeypatch.setattr(ollama_module.ollama, "chat", _chat_returning(LLM_OUTPUT))
        assert _gemma(_FakeClient(default=1)).improve(TEXT) == LIGHT_OUTPUT

    def test_degradation_returns_light_mode_correction(self, monkeypatch):
        monkeypatch.setattr(ollama_module, "should_accept_correction", _gate(True))
        monkeypatch.setattr(ollama_module.ollama, "chat", _chat_returning(LLM_OUTPUT))
        client = _FakeClient(errors={TEXT: 1, LLM_OUTPUT: 5})
        assert _gemma(client).improve(TEXT) == LIGHT_OUTPUT

    def test_ollama_error_returns_light_mode_correction(self, monkeypatch):
        monkeypatch.setattr(ollama_module, "should_accept_correction", _gate(True))
        monkeypatch.setattr(ollama_module.ollama, "chat", _chat_raising)
        assert _gemma(_FakeClient()).improve(TEXT) == LIGHT_OUTPUT

    def test_an_accepted_output_is_returned_as_is(self, monkeypatch):
        monkeypatch.setattr(ollama_module, "should_accept_correction", _gate(True))
        monkeypatch.setattr(ollama_module.ollama, "chat", _chat_returning(LLM_OUTPUT))
        client = _FakeClient(errors={TEXT: 2, LLM_OUTPUT: 0})
        assert _gemma(client).improve(TEXT) == LLM_OUTPUT


class TestSharedClient:
    def test_a_light_improver_does_not_close_a_client_it_was_lent(self):
        client = _FakeClient()
        LTImprover("fr", "http://unused", client=client).close()
        assert client.closed is False

    def test_a_light_improver_closes_a_client_it_created(self, monkeypatch):
        import src.improvers.lt_improver as lt_module

        created = _FakeClient()
        monkeypatch.setattr(lt_module, "LTClient", lambda *args, **kwargs: created)
        LTImprover("fr", "http://unused").close()
        assert created.closed is True
