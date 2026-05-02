"""lib/theme.py — Stylesheet installation.

Loads ``assets/rgf.css`` once per session and injects it via
``st.markdown(unsafe_allow_html=True)``. The CSS file is a template:
every ``{TOKEN}`` placeholder gets replaced with a value from
``lib.tokens.tokens_dict()`` so palette / radii / sidebar dims live
in one place (Python) and propagate to the stylesheet.

Public surface:
    ``install_theme()``  — call once at the top of ``app.py``.
"""
from __future__ import annotations

import streamlit as st

from lib.tokens import PROJECT_ROOT, tokens_dict


_CSS_PATH = PROJECT_ROOT / "assets" / "rgf.css"


# ``mtime`` is a cache key — when the CSS file changes on disk, the mtime
# changes, Streamlit's @cache_resource treats it as a new function call
# and re-reads the template. Without this, edits to ``assets/rgf.css``
# only took effect on a full ``streamlit run`` restart.
@st.cache_resource
def _load_css(mtime: float = 0.0) -> str:
    template = _CSS_PATH.read_text(encoding="utf-8")
    return template.format_map(tokens_dict())


def install_theme() -> None:
    """Inject the CSS template. Re-reads from disk if the file changed."""
    mtime = _CSS_PATH.stat().st_mtime
    st.markdown(f"<style>{_load_css(mtime)}</style>", unsafe_allow_html=True)
