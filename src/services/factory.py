# src/services/factory.py
import streamlit as st
from pathlib import Path
from src.utils.config import load_config
from src.guardrails.spacy_loader import load_french_nlp
from src.improvers.lt_improver import LTImprover
from src.improvers.llm_improver import LLMImprover

@st.cache_resource
def get_config():
    return load_config()

@st.cache_resource
def get_nlp(cfg):
    spacy_cfg = cfg["spacy"]
    return load_french_nlp(
        spacy_cfg["model"],
        only_ner_pos=spacy_cfg.get("only_ner_pos", True),
        add_date_ruler=spacy_cfg.get("add_date_ruler", False),
    )

@st.cache_resource
def get_lt_improver(_cfg, _nlp):
    # Note: Underscore arguments (_cfg) tells Streamlit not to hash them for caching
    server_url = f"http://{_cfg['lt']['server']['host']}:{_cfg['lt']['server']['port']}"
    return LTImprover(lang=_cfg['lt']['lang'], server_url=server_url, nlp=_nlp)

@st.cache_resource
def get_llm_improver(_cfg, _nlp, model_key: str):
    """
    Loads an LLM based on the key provided (e.g., 'mistral' or 'gemma').
    """
    # 1. Get specific model config
    if model_key not in _cfg['llm']:
         raise ValueError(f"Configuration not found for model: {model_key}")
         
    model_conf = _cfg['llm'][model_key]
    
    # 2. Build path
    model_path = Path(_cfg['llm']['models_dir']) / model_conf['filename']
    
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    # 3. Initialize
    # We pass the LT server URL dynamically
    lt_url = f"http://{_cfg['lt']['server']['host']}:{_cfg['lt']['server']['port']}"
    
    return LLMImprover(
        model_path=str(model_path),
        lang=_cfg['lt']['lang'],
        lt_server_url=lt_url,
        nlp=_nlp,
        n_ctx=model_conf.get('n_ctx', 2048),
        max_tokens=model_conf.get('max_tokens', 512),
        temperature=model_conf.get('temperature', 0.1),
    )