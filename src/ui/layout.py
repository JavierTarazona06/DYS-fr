# src/ui/layout.py
import streamlit as st
from src.ui.content import Content

# Try importing the diff library, handle case where it's missing
try:
    import diff_match_patch as dmp_module
    HAS_DMP = True
except ImportError:
    HAS_DMP = False

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
    
    if mode == Content.MODE_HYBRID:
        model_choice_label = st.sidebar.radio(
            "Modèle IA",
            ["Mistral 7B (Local GGUF)", "Gemma 3 (Ollama)"],
            index=1,
            help="Mistral tourne dans l'app. Gemma nécessite Ollama installé."
        )
        if "Gemma" in model_choice_label:
            model_choice = "gemma"
        else:
            model_choice = "mistral"
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(Content.ABOUT_TITLE)
    st.sidebar.markdown(Content.ABOUT_TEXT)
    
    return mode, model_choice

def _generate_html_diff(text1: str, text2: str) -> str:
    """
    Generates an HTML string with inline diffs using diff-match-patch.
    """
    dmp = dmp_module.diff_match_patch()
    
    # Calculate difference
    diffs = dmp.diff_main(text1, text2)
    # Cleanup to make it look more like human edits (semantic cleanup)
    dmp.diff_cleanupSemantic(diffs)
    
    html = []
    # CSS styles for the view
    html.append("<div style='line-height: 1.8; font-family: sans-serif; font-size: 16px; border: 1px solid #ddd; padding: 15px; border-radius: 5px; background-color: #fafafa;'>")
    
    for op, data in diffs:
        # Escape HTML characters in data to prevent injection/rendering issues
        text = data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        
        if op == 0: # Equal (No change)
            html.append(f"<span style='color: #333;'>{text}</span>")
            
        elif op == 1: # Insert (Green)
            html.append(f"<strong style='background-color: #d4edda; color: #155724; border-radius: 3px; padding: 0 2px;'>{text}</strong>")
            
        elif op == -1: # Delete (Red)
            html.append(f"<span style='background-color: #f8d7da; color: #721c24; text-decoration: line-through; opacity: 0.8; padding: 0 2px;'>{text}</span>")
            
    html.append("</div>")
    return "".join(html)

def render_diff_view(original: str, corrected: str):
    """Renders the before/after view using HTML diff if available."""
    
    with st.expander(Content.SECTION_DIFF, expanded=True):
        if HAS_DMP:
            st.markdown("### 🔍 Comparaison visuelle")
            st.caption("Vert = Ajouté/Modifié | Rouge = Supprimé")
            diff_html = _generate_html_diff(original, corrected)
            st.markdown(diff_html, unsafe_allow_html=True)
            
            # Optional: Show clean raw text below for copying
            st.markdown("---")
            st.markdown("**Texte final propre :**")
            st.code(corrected, language=None)
            
        else:
            # Fallback if library not installed
            st.warning("Installez 'diff-match-patch' pour voir les différences en couleur.")
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