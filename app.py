import streamlit as st
from src.ui.content import Content
from src.ui import layout
from src.services import factory

# 1. Page Setup
st.set_page_config(page_title="DYS-fr", layout="wide", page_icon="🧠")

# 2. Load Resources (Cached)
try:
    cfg = factory.get_config()
    nlp = factory.get_nlp(cfg)
except Exception as e:
    st.error(f"Critical System Error: {e}")
    st.stop()

# 3. Render Sidebar & Get User Input
mode, model_key = layout.render_sidebar()

# 4. Initialize the correct Improver
improver = None

if mode == Content.MODE_LIGHT:
    improver = factory.get_lt_improver(cfg, nlp)
    st.sidebar.success(f"✓ {Content.MODE_LIGHT} actif")
    
else: # Hybrid Mode
    try:
        with st.spinner(f"⏳ Chargement de l'IA ({model_key})..."):
            improver = factory.get_llm_improver(cfg, nlp, model_key)
        st.sidebar.success(f"✓ {Content.MODE_HYBRID} actif")
        
    except FileNotFoundError as e:
        layout.show_error(Content.ERR_MODEL_NOT_FOUND, e, Content.install_instructions(model_key))
        st.stop()
    except Exception as e:
        layout.show_error("Erreur technique", e)
        st.stop()

# 5. Main Content Area
layout.render_header()

text = st.text_area(
    Content.INPUT_LABEL,
    height=220,
    value="Je sui aller au supermarchet pour achète du pin et du lais, mes la caissiere a fermer la caise a 18h et jai dus rentré sans rien.",
    help=Content.INPUT_HELP,
    placeholder=Content.INPUT_PLACEHOLDER
)

if st.button(Content.BTN_CORRECT, type="primary"):
    if not text.strip():
        st.warning(Content.ERR_NO_TEXT)
    else:
        with st.spinner("🔄 Correction en cours..."):
            # Run improvement
            # We assume Hybrid mode implies debug=False for production feel, 
            # but you can add a debug toggle in sidebar if needed.
            is_hybrid = (mode == Content.MODE_HYBRID)
            out = improver.improve(text)
        
        st.subheader(Content.SECTION_RESULT)
        st.success(out)
        
        layout.render_diff_view(text, out)

# No cleanup needed for Streamlit resources