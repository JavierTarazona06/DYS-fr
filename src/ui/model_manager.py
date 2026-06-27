"""Sidebar panel for downloading the local LLM model.

The installer ships no GGUF, so this is how a user reaches hybrid mode. The download
runs on a background thread owned by ``@st.cache_resource`` so it survives the script
reruns Streamlit performs on every widget interaction; progress is polled by a
fragment, which keeps the rest of the app usable in light mode meanwhile.
"""

from __future__ import annotations

import streamlit as st

from src.services import factory, model_catalog
from src.services.model_downloader import ModelDownloader
from src.ui.content import Content


@st.cache_resource
def _get_downloader() -> ModelDownloader:
    """One downloader per server process, immune to script reruns."""
    return ModelDownloader()


def _total_ram_gb() -> int | None:
    try:
        import psutil

        return round(psutil.virtual_memory().total / (1024**3))
    except Exception:
        return None


@st.fragment(run_every=1.0)
def _render_progress() -> None:
    downloader = _get_downloader()
    state = downloader.state()

    with st.sidebar:
        if state.status == "verifying":
            st.progress(1.0, text=Content.DL_VERIFYING)
        else:
            st.progress(
                state.fraction,
                text=Content.download_progress(state.downloaded_bytes, state.total_bytes),
            )
        st.button(Content.BTN_CANCEL_DOWNLOAD, key="dys_cancel_download", on_click=downloader.cancel)

    if state.status in {"done", "error", "cancelled"}:
        # The capabilities are cached, so without clearing them the mode selector
        # would keep hiding hybrid mode until the application restarts.
        factory.get_runtime_capabilities.clear()
        st.rerun(scope="app")


def render_model_panel(cfg: dict, capabilities: dict) -> None:
    """Render the download panel in the sidebar. No-op when nothing is actionable."""
    downloader = _get_downloader()
    state = downloader.state()

    if downloader.is_running():
        _render_progress()
        return

    if not capabilities.get("llama_cpp_available"):
        # A basic-flavour build: downloading a model would not help.
        return

    pending = capabilities.get("downloadable_models") or []

    if state.status == "done" and not pending:
        st.sidebar.success(Content.DL_DONE)
        return
    if not pending:
        return

    with st.sidebar.expander(Content.MODEL_PANEL_TITLE, expanded=True):
        if state.status == "error":
            st.error(state.message)
        elif state.status == "cancelled":
            st.info(Content.DL_CANCELLED)
        else:
            st.caption(Content.MODEL_NOT_INSTALLED)

        for entry in pending:
            label = entry.get("display_name", entry["id"])
            size = entry.get("size_bytes") or 0
            st.write(f"**{label}** — {Content.download_size(size)}" if size else f"**{label}**")

            required_gb = entry.get("min_ram_gb")
            available_gb = _total_ram_gb()
            if required_gb and available_gb and available_gb < required_gb:
                st.warning(Content.ram_warning(required_gb, available_gb))

            if st.button(Content.BTN_DOWNLOAD_MODEL, key=f"dys_download_{entry['id']}"):
                fresh = model_catalog.get_entry(cfg, entry["id"]) or entry
                downloader.start(fresh, model_catalog.download_destination())
                st.rerun()
