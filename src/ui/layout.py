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
    
    # Only show model selector if in Hybrid mode (We will add the selector logic here later)
    model_choice = "mistral" # Default for now
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(Content.ABOUT_TITLE)
    st.sidebar.markdown(Content.ABOUT_TEXT)
    
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