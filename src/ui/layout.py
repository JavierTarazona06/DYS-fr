# src/ui/layout.py
import streamlit as st
from src.ui.content import Content

def render_header():
    st.title(Content.APP_TITLE)
    st.markdown(Content.APP_SUBTITLE)

def render_sidebar():
    """Renders sidebar and returns the selected options."""
    st.sidebar.title(Content.SIDEBAR_TITLE)
    
    mode = st.sidebar.selectbox(
        Content.MODE_LABEL,
        [Content.MODE_LIGHT, Content.MODE_HYBRID],
        help=Content.MODE_HELP
    )
    
    model_choice = "mistral" # Default
    
    # SHOW SELECTOR IF HYBRID
    if mode == Content.MODE_HYBRID:
        model_choice_label = st.sidebar.radio(
            "Modèle IA",
            ["Mistral 7B (Local GGUF)", "Gemma 3 (Ollama)"],
            index=1, # Default to Gemma
            help="Mistral tourne dans l'app. Gemma nécessite Ollama installé."
        )
        
        # Map label to config key
        if "Gemma" in model_choice_label:
            model_choice = "gemma"
        else:
            model_choice = "mistral"
    
    st.sidebar.markdown("---")
    
    # --- RESTORED SECTION ---
    st.sidebar.markdown(Content.ABOUT_TITLE)
    st.sidebar.markdown(Content.ABOUT_TEXT)
    # ------------------------
    
    return mode, model_choice

def render_diff_view(original: str, corrected: str):
    """Renders the before/after view."""
    with st.expander(Content.SECTION_DIFF):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Avant:**")
            st.code(original, language=None)
        with col2:
            st.markdown("**Après:**")
            st.code(corrected, language=None)

def show_error(title, exception, instructions=None):
    st.error(f"**{title}**")
    st.error(str(exception))
    if instructions:
        st.info(instructions)