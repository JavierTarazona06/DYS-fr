import os, streamlit as st
from src.utils.config import load_config
from src.improvers.lt_improver import LTImprover

st.set_page_config(page_title="DYS-fr (POC)", layout="wide")

cfg = load_config()
server_url = os.getenv("LT_URL", f"http://{cfg['lt']['server']['host']}:{cfg['lt']['server']['port']}")
lang = os.getenv("LT_LANG", cfg["lt"]["lang"])

@st.cache_resource
def _get_improver():
    return LTImprover(lang=lang, server_url=server_url)

improver = _get_improver()

st.title("DYS-fr · POC LT improver")
text = st.text_area("Texte d’entrée", height=220, value="Departement of meeddicine Colombia University closed on August 1 Milinda Samuelli")
if st.button("Améliorer"):
    out = improver.improve(text)
    st.subheader("Sortie")
    st.code(out)

# Streamlit will keep the resource alive; optional cleanup on stop not needed here.