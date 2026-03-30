# src/services/factory.py
import streamlit as st
from pathlib import Path
from src.utils.config import load_config
from src.guardrails.spacy_loader import load_french_nlp

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

@st.cache_resource
def get_lt_improver(_cfg, _nlp):
    # Note: Underscore arguments (_cfg) tells Streamlit not to hash them for caching
    from src.improvers.lt_improver import LTImprover

    server_url = f"http://{_cfg['lt']['server']['host']}:{_cfg['lt']['server']['port']}"
    lt_client_cfg = _cfg.get('lt', {}).get('client', {})
    return LTImprover(
        lang=_cfg['lt']['lang'],
        server_url=server_url,
        nlp=_nlp,
        lt_config=lt_client_cfg,
    )

@st.cache_resource
def get_llm_improver(_cfg, _nlp, model_key: str):
    """
    Loads an LLM. 
    If model_key is 'mistral', loads embedded GGUF.
    If model_key is 'gemma', connects to Ollama.
    """
    lt_url = f"http://{_cfg['lt']['server']['host']}:{_cfg['lt']['server']['port']}"
    lt_client_cfg = _cfg.get('lt', {}).get('client', {})
    validate_with_lt_after = _cfg.get('llm', {}).get('validate_with_lt_after', False)
    
    # --- GEMMA (OLLAMA) ---
    if model_key == "gemma":
        from src.improvers.ollama_improver import OllamaImprover

        conf = _cfg['llm']['gemma']
        return OllamaImprover(
            model_name=conf['model_name'],
            lang=_cfg['lt']['lang'],
            lt_server_url=lt_url,
            nlp=_nlp,
            lt_config=lt_client_cfg,
            validate_with_lt_after=conf.get('validate_with_lt_after', validate_with_lt_after),
            temperature=conf.get('temperature', 0.1),
            num_ctx=conf.get('num_ctx', 2048),
            num_predict=conf.get('num_predict', 256),
            top_p=conf.get('top_p', 0.9),
        )

    # --- MISTRAL (EMBEDDED) ---
    elif model_key == "mistral":
        from src.improvers.llm_improver import LLMImprover

        conf = _cfg['llm']['mistral']
        model_path = Path(_cfg['llm']['models_dir']) / conf['filename']
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        return LLMImprover(
            model_path=str(model_path),
            lang=_cfg['lt']['lang'],
            lt_server_url=lt_url,
            nlp=_nlp,
            lt_config=lt_client_cfg,
            validate_with_lt_after=conf.get('validate_with_lt_after', validate_with_lt_after),
            n_ctx=conf.get('n_ctx', 2048),
            max_tokens=conf.get('max_tokens', 512),
            temperature=conf.get('temperature', 0.1),
        )
    
    else:
        raise ValueError(f"Unknown model key: {model_key}")
