import os, streamlit as st
from src.utils.config import load_config
from src.guardrails.spacy_loader import load_french_nlp
from src.improvers.lt_improver import LTImprover

st.set_page_config(page_title="DYS-fr (POC)", layout="wide")

cfg = load_config()
server_url = os.getenv("LT_URL", f"http://{cfg['lt']['server']['host']}:{cfg['lt']['server']['port']}")
lang = os.getenv("LT_LANG", cfg["lt"]["lang"])

@st.cache_resource
def _get_nlp():
    spacy_cfg = cfg["spacy"]
    return load_french_nlp(
        spacy_cfg["model"],
        only_ner_pos=spacy_cfg.get("only_ner_pos", True),
        add_date_ruler=spacy_cfg.get("add_date_ruler", False),
    )

@st.cache_resource
def _get_improver():
    nlp = _get_nlp()
    # No need to pass lt_config={} here if LTClient is reverted to not use it for 'level'
    return LTImprover(lang=lang, server_url=server_url, nlp=nlp)

improver = _get_improver()

st.title("DYS-fr · POC LT improver")
text = st.text_area("Texte d’entrée", height=220, value="Je sui aller au supermarchet pour achète du pin et du lais, mes la caissiere a fermer la caise a 18h et jai dus rentré sans rien \n Je sui aller au supermarchet avec Marie Dubois pour achete du pin et du lais")
if st.button("Améliorer"):
    out = improver.improve(text)
    st.subheader("Sortie")
    st.code(out)

# Streamlit will keep the resource alive; optional cleanup on stop not needed here.