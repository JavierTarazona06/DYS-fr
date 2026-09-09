# src/ui/layout.py
import os

import streamlit as st

from src.ui.content import Content

try:
    import diff_match_patch as dmp_module

    HAS_DMP = True
except ImportError:
    HAS_DMP = False


def render_header():
    st.title(Content.APP_TITLE)
    st.markdown(Content.APP_SUBTITLE)


def render_sidebar(capabilities: dict):
    """Render sidebar and return the selected mode plus model key."""
    st.sidebar.title(Content.SIDEBAR_TITLE)

    if os.getenv("DYS_FR_UI_PORT_FALLBACK") == "1":
        st.sidebar.warning(Content.port_fallback(os.getenv("DYS_FR_UI_URL", "")))

    mode_options = [Content.MODE_LIGHT]
    if capabilities.get("hybrid_available"):
        mode_options.append(Content.MODE_HYBRID)

    mode = st.sidebar.selectbox(
        Content.MODE_LABEL,
        mode_options,
        help=Content.MODE_HELP,
    )

    model_choice = None
    available_models = capabilities.get("available_models", [])

    if mode == Content.MODE_HYBRID and available_models:
        labels = [item["label"] for item in available_models]
        selected_label = st.sidebar.radio(
            Content.MODEL_LABEL,
            labels,
            index=0,
            help=Content.MODEL_HELP,
        )
        label_to_key = {item["label"]: item["key"] for item in available_models}
        model_choice = label_to_key[selected_label]
    elif not capabilities.get("hybrid_available"):
        st.sidebar.info(Content.HYBRID_UNAVAILABLE)
        for reason in capabilities.get("reasons", []):
            st.sidebar.caption(reason)

    st.sidebar.markdown("---")
    st.sidebar.markdown(Content.ABOUT_TITLE)
    st.sidebar.markdown(Content.ABOUT_TEXT)

    return mode, model_choice


def _generate_html_diff(text1: str, text2: str, appearance=None) -> str:
    """Inline diff as HTML, honouring the reader's typography settings.

    This used to hardcode font, size, line-height and colours in inline `style=`
    attributes, which win the CSS cascade — so this one function silently overrode every
    reading-comfort setting, in the one place a dyslexic reader compares text most closely.
    """
    line_height = getattr(appearance, "line_height", 1.6)

    dmp = dmp_module.diff_match_patch()

    diffs = dmp.diff_main(text1, text2)
    dmp.diff_cleanupSemantic(diffs)

    html = []
    # No font-family or font-size: both are inherited, so the root override applies here
    # like everywhere else.
    html.append(
        f"<div style='line-height: {line_height}; border: 1px solid #ddd; "
        "padding: 15px; border-radius: 5px;'>"
    )

    for op, data in diffs:
        text = data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

        if op == 0:
            html.append(f"<span>{text}</span>")
        elif op == 1:
            # E6 asks for underline, not bold: underline survives a high-contrast theme
            # and does not rely on colour alone to carry meaning.
            html.append(
                "<span style='background-color: #d4edda; color: #155724; "
                f"text-decoration: underline; padding: 0 2px;'>{text}</span>"
            )
        elif op == -1:
            # The opacity this used to carry lowered contrast on deleted text, which is
            # exactly the text the reader is trying to compare.
            html.append(
                "<span style='background-color: #f8d7da; color: #721c24; "
                f"text-decoration: line-through; padding: 0 2px;'>{text}</span>"
            )

    html.append("</div>")
    return "".join(html)


def render_diff_view(original: str, corrected: str, appearance=None):
    """Render the before/after diff view."""
    with st.expander(Content.SECTION_DIFF, expanded=True):
        if HAS_DMP:
            st.markdown("### Comparaison visuelle")
            st.caption("Vert = Ajouté/Modifié | Rouge = Supprimé")
            diff_html = _generate_html_diff(original, corrected, appearance)
            st.markdown(diff_html, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("**Texte final propre :**")
            st.code(corrected, language=None)
        else:
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
