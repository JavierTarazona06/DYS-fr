"""Reading comfort settings: text size, line spacing, and a distraction-free mode.

Rules E2, E3 and E5. The product exists for dyslexic readers, and until now the interface
offered them no control at all over how text is presented.

**Everything here is CSS injection, and that is forced rather than chosen.** Streamlit 1.51
has a complete theming system, but all fifty of its options are registered
`scriptable=False`: `st.set_option("theme.font", ...)` raises `StreamlitAPIException`.
Theme configuration is a launch-time baseline only, so anything the user toggles while the
app is running has to be a stylesheet.

Settings persist to `%LOCALAPPDATA%\\DYS-fr\\config.yaml`. For an accessibility feature that
is not a nicety: making someone re-pick their text size at every launch defeats the point.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

import streamlit as st

from src.ui.content import Content
from src.utils.config import save_user_config

#: Neutral defaults, matching Streamlit's own baseline. A deliberate product decision:
#: the application does not impose a dyslexia-optimised look, it offers one.
DEFAULT_FONT_SIZE_PX = 16
DEFAULT_LINE_HEIGHT = 1.6

FONT_SIZE_RANGE = (14, 28)
#: WCAG 1.4.12 asks for at least 1.5x; the range starts below it so the setting can also be
#: used to fit more text on screen, and the default already satisfies the guideline.
LINE_HEIGHT_RANGE = (1.2, 2.4)

_SESSION_KEY = "dys_appearance"


@dataclass(frozen=True)
class Appearance:
    font_size_px: int = DEFAULT_FONT_SIZE_PX
    line_height: float = DEFAULT_LINE_HEIGHT
    focus_mode: bool = False

    @classmethod
    def from_config(cls, cfg: dict) -> "Appearance":
        stored = (cfg.get("ui") or {}).get("appearance") or {}
        return cls(
            font_size_px=int(stored.get("font_size_px", DEFAULT_FONT_SIZE_PX)),
            line_height=float(stored.get("line_height", DEFAULT_LINE_HEIGHT)),
            focus_mode=bool(stored.get("focus_mode", False)),
        )

    def is_default(self) -> bool:
        return self == Appearance()


def _has_stored_settings(cfg: dict) -> bool:
    """Whether the user has ever saved a preference, as opposed to running on defaults."""
    return bool((cfg.get("ui") or {}).get("appearance"))


def current(cfg: dict) -> Appearance:
    """The active settings, from session state if the user has touched them this run."""
    if _SESSION_KEY not in st.session_state:
        st.session_state[_SESSION_KEY] = Appearance.from_config(cfg)
    return st.session_state[_SESSION_KEY]


def _store(appearance: Appearance) -> None:
    st.session_state[_SESSION_KEY] = appearance
    try:
        save_user_config({"ui": {"appearance": asdict(appearance)}})
    except OSError:
        # A read-only or full profile must not stop the user changing their text size for
        # this session; it only means the choice will not survive a restart.
        pass


def build_css(appearance: Appearance) -> str:
    """The stylesheet for the current settings.

    Streamlit's frontend expresses every size in `rem`, so overriding the root font size
    scales the whole interface — widgets, buttons and body text together — rather than only
    the paragraphs. That is why E2 is three lines rather than a per-element sweep.
    """
    rules = [
        f"html {{ font-size: {appearance.font_size_px}px; }}",
        (
            '[data-testid="stAppViewContainer"], [data-testid="stMarkdownContainer"], '
            f'.stTextArea textarea {{ line-height: {appearance.line_height}; }}'
        ),
    ]

    if appearance.focus_mode:
        rules.append(
            '[data-testid="stHeader"], [data-testid="stToolbar"], '
            '[data-testid="stMainMenu"], [data-testid="stDecoration"] '
            "{ display: none !important; }"
        )
        # The sidebar goes too. Note what this does NOT buy: hiding it with display:none
        # leaves Streamlit believing the sidebar is still expanded, so it never renders its
        # own collapsed control. Verified in the browser — the element does not exist. That
        # is why focus mode ships its own exit button; without one the user is stranded
        # with no route back to these settings.
        rules.append('[data-testid="stSidebar"] { display: none !important; }')

    return "<style>\n" + "\n".join(rules) + "\n</style>"


def apply(cfg: dict) -> Appearance:
    """Emit the stylesheet. Call once, before anything else renders.

    Placed at the top of `app.py` on purpose: the boot status and the error screens render
    before the sidebar exists, and a dyslexic user should not meet an unstyled wait screen.
    """
    appearance = current(cfg)
    st.html(build_css(appearance))

    if appearance.focus_mode:
        # The only way back: the sidebar holding the settings is hidden, and Streamlit
        # offers nothing native once it is hidden this way.
        if st.button(Content.APPEARANCE_FOCUS_EXIT, key="dys_exit_focus"):
            _store(replace(appearance, focus_mode=False))
            st.rerun()

    return appearance


def render_panel(cfg: dict) -> None:
    """The settings panel. Belongs in the sidebar, next to the engine controls."""
    appearance = current(cfg)

    # Open on the very first run so the controls are discoverable: with neutral defaults,
    # whether this tool is comfortable to read depends on the user finding this panel once.
    #
    # The decision is made once per session and then held constant. Streamlit re-applies
    # `expanded` whenever the value *changes* between runs, so a computed flag fights the
    # user — the panel snapped shut on every rerun, including the one triggered by moving
    # a slider inside it.
    if "dys_appearance_expanded" not in st.session_state:
        st.session_state["dys_appearance_expanded"] = not _has_stored_settings(cfg)
    expanded = st.session_state["dys_appearance_expanded"]

    with st.sidebar.expander(Content.APPEARANCE_TITLE, expanded=expanded):
        font_size = st.slider(
            Content.APPEARANCE_FONT_SIZE,
            min_value=FONT_SIZE_RANGE[0],
            max_value=FONT_SIZE_RANGE[1],
            value=appearance.font_size_px,
            step=1,
            help=Content.APPEARANCE_FONT_SIZE_HELP,
        )
        line_height = st.slider(
            Content.APPEARANCE_LINE_HEIGHT,
            min_value=LINE_HEIGHT_RANGE[0],
            max_value=LINE_HEIGHT_RANGE[1],
            value=appearance.line_height,
            step=0.1,
            help=Content.APPEARANCE_LINE_HEIGHT_HELP,
        )
        focus_mode = st.checkbox(
            Content.APPEARANCE_FOCUS,
            value=appearance.focus_mode,
            help=Content.APPEARANCE_FOCUS_HELP,
        )

        if st.button(Content.APPEARANCE_RESET, disabled=appearance.is_default()):
            _store(Appearance())
            st.rerun()

    updated = Appearance(
        font_size_px=int(font_size), line_height=float(line_height), focus_mode=bool(focus_mode)
    )
    if updated != appearance:
        _store(updated)
        st.rerun()
