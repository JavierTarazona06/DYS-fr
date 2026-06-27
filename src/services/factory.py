# src/services/factory.py
from __future__ import annotations

import os
import urllib.request
from importlib.util import find_spec

import streamlit as st

from src.guardrails.spacy_loader import load_french_nlp
from src.services import model_catalog
from src.improvers.lt_improver import LTImprover
from src.utils.config import load_config
from src.utils.paths import find_model_file


def _resolve_lt_runtime_settings(cfg: dict) -> tuple[str, str]:
    default_url = f"http://{cfg['lt']['server']['host']}:{cfg['lt']['server']['port']}"
    return (
        os.getenv("LT_URL", default_url),
        os.getenv("LT_LANG", cfg["lt"]["lang"]),
    )


def _resolve_mistral_model_path(cfg: dict) -> tuple[str | None, list[str]]:
    mistral_cfg = cfg.get("llm", {}).get("mistral", {})
    filename = mistral_cfg.get("filename")
    if not filename:
        return None, []

    model_path, candidates = find_model_file(cfg["llm"]["models_dir"], filename)
    return (str(model_path) if model_path else None, [str(candidate) for candidate in candidates])


@st.cache_resource
def get_config():
    return load_config()


@st.cache_resource
def get_nlp(cfg):
    spacy_cfg = cfg["spacy"]
    return load_french_nlp(
        spacy_cfg["model"],
        target_dir=spacy_cfg.get("target_dir"),
        only_ner_pos=spacy_cfg.get("only_ner_pos", True),
        add_date_ruler=spacy_cfg.get("add_date_ruler", False),
    )


def probe_lt(cfg, timeout_s: float = 0.5) -> bool:
    """Cheap liveness check for the LanguageTool server.

    Deliberately uncached and deliberately not routed through LTClient: that
    constructor issues a request with a 5s timeout and raises on failure, which
    would stall every poll while the JVM is still starting.
    """
    lt_url, _ = _resolve_lt_runtime_settings(cfg)
    try:
        with urllib.request.urlopen(f"{lt_url}/v2/languages", timeout=timeout_s) as response:
            return response.status == 200
    except Exception:
        return False


@st.cache_data
def get_runtime_capabilities(cfg):
    available_models = []
    reasons = []

    mistral_path, mistral_candidates = _resolve_mistral_model_path(cfg)
    if find_spec("llama_cpp") and mistral_path:
        available_models.append(
            {
                "key": "mistral",
                "label": "Mistral 7B (Local GGUF)",
                "description": "Modèle local embarqué.",
            }
        )
    elif find_spec("llama_cpp") and not mistral_path:
        reasons.append("Mistral est indisponible: le fichier GGUF est absent.")

    if find_spec("ollama"):
        available_models.append(
            {
                "key": "gemma",
                "label": "Gemma 3 (Ollama)",
                "description": "Backend externe via Ollama.",
            }
        )
    else:
        reasons.append("Gemma est indisponible: le client Python Ollama n'est pas installé.")

    return {
        "hybrid_available": bool(available_models),
        "available_models": available_models,
        "reasons": reasons,
        "mistral_candidates": mistral_candidates,
        # Lets the UI tell "this build has no AI engine" (nothing the user can do)
        # apart from "the model is not downloaded yet" (offer the download button).
        "llama_cpp_available": bool(find_spec("llama_cpp")),
        "downloadable_models": model_catalog.missing_entries(cfg),
    }


@st.cache_resource
def get_lt_improver(_cfg, _nlp):
    lt_url, lt_lang = _resolve_lt_runtime_settings(_cfg)
    return LTImprover(lang=lt_lang, server_url=lt_url, nlp=_nlp)


@st.cache_resource
def get_llm_improver(_cfg, _nlp, model_key: str):
    lt_url, lt_lang = _resolve_lt_runtime_settings(_cfg)

    if model_key == "gemma":
        from src.improvers.ollama_improver import OllamaImprover

        conf = _cfg["llm"]["gemma"]
        return OllamaImprover(
            model_name=conf["model_name"],
            lang=lt_lang,
            lt_server_url=lt_url,
            nlp=_nlp,
            temperature=conf.get("temperature", 0.1),
        )

    if model_key == "mistral":
        from src.improvers.llm_improver import LLMImprover

        conf = _cfg["llm"]["mistral"]
        model_path, candidates = _resolve_mistral_model_path(_cfg)
        if not model_path:
            pretty_candidates = "\n".join(f"- {candidate}" for candidate in candidates)
            raise FileNotFoundError(
                "Model file not found. Looked in:\n"
                f"{pretty_candidates or '- no candidate paths configured'}"
            )

        return LLMImprover(
            model_path=model_path,
            lang=lt_lang,
            lt_server_url=lt_url,
            nlp=_nlp,
            n_ctx=conf.get("n_ctx", 2048),
            max_tokens=conf.get("max_tokens", 512),
            temperature=conf.get("temperature", 0.1),
        )

    raise ValueError(f"Unknown model key: {model_key}")
