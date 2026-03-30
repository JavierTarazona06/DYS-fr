import streamlit as st

from src.services import factory
from src.ui import layout
from src.ui.content import Content

st.set_page_config(page_title="DYS-fr", layout="wide", page_icon="🧠")

try:
    cfg = factory.get_config()
    nlp = factory.get_nlp(cfg)
    capabilities = factory.get_runtime_capabilities(cfg)
except Exception as exc:
    st.error(f"Critical System Error: {exc}")
    st.stop()

mode, model_key = layout.render_sidebar(capabilities)

improver = None
if mode == Content.MODE_LIGHT:
    improver = factory.get_lt_improver(cfg, nlp)
    st.sidebar.success(f"{Content.MODE_LIGHT} actif")
else:
    if not model_key:
        layout.show_error("Configuration IA", RuntimeError("Aucun modèle IA disponible pour cette installation."))
        st.stop()

    try:
        with st.spinner(f"Chargement de l'IA ({model_key})..."):
            improver = factory.get_llm_improver(cfg, nlp, model_key)
        st.sidebar.success(f"{Content.MODE_HYBRID} actif")
    except FileNotFoundError as exc:
        layout.show_error(Content.ERR_MODEL_NOT_FOUND, exc, Content.install_instructions(model_key))
        st.stop()
    except Exception as exc:
        layout.show_error("Erreur technique", exc)
        st.stop()

layout.render_header()

text = st.text_area(
    Content.INPUT_LABEL,
    height=220,
    value=(
        "Je sui aller au supermarchet pour achète du pin et du lais, "
        "mes la caissiere a fermer la caise a 18h et jai dus rentré sans rien."
    ),
    help=Content.INPUT_HELP,
    placeholder=Content.INPUT_PLACEHOLDER,
)

if st.button(Content.BTN_CORRECT, type="primary"):
    if not text.strip():
        st.warning(Content.ERR_NO_TEXT)
    else:
        with st.spinner("Correction en cours..."):
            out = improver.improve(text)

        st.subheader(Content.SECTION_RESULT)
        st.success(out)
        layout.render_diff_view(text, out)
