"""SHM Dashboard — Streamlit entry point.

Long-term Structural Health Monitoring data (LVDTs, tiltmeters,
thermocouples) over days / weeks / months. Renders the app shell
(sidebar, hidden trigger buttons, JS bridge) and dispatches to the
active view. Most of the heavy lifting lives in sibling modules:

  ``lib.shell``    — sidebar HTML, NAV table, footer
  ``lib.bridge``   — JS click-dispatch (visible HTML → hidden ``st.button``)
  ``lib.theme``    — CSS template loader
  ``lib.shm``      — domain logic (column classification, anomalies, drift)
  ``views/*.py``   — one module per top-level view
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="RGF SHM Monitoring",
    page_icon=":material/sensors:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from lib.bridge import inject_click_bridge
from lib.cache import ensure_all_imported_registered
from lib.shell import NAV, VALID_VIEW_IDS, render_sidebar
from lib.state import hydrate_from_disk, imported_tables, session_id
from lib.theme import install_theme


install_theme()
session_id()
hydrate_from_disk()
ensure_all_imported_registered(imported_tables())


# ── Active view from URL or default ─────────────────────────────────────────
if "view" not in st.session_state:
    qp = st.query_params.get("view", "dashboard")
    if isinstance(qp, list):
        qp = qp[0] if qp else "dashboard"
    st.session_state.view = qp if qp in VALID_VIEW_IDS else "dashboard"

active_view = st.session_state.view


# ── Sidebar collapse state ──────────────────────────────────────────────────
if "sidebar_collapsed" not in st.session_state:
    st.session_state.sidebar_collapsed = False
if st.button("·", key="__sidebar_toggle"):
    st.session_state.sidebar_collapsed = not st.session_state.sidebar_collapsed
    st.rerun()


# ── Hidden trigger buttons (one per nav item) ──────────────────────────────
for vid, _label, _icon in NAV:
    if st.button("·", key=f"__nav_{vid}"):
        st.session_state.view = vid
        st.query_params["view"] = vid
        st.rerun()


# ── Visible sidebar + JS bridge ─────────────────────────────────────────────
render_sidebar(active_view)
inject_click_bridge()


# ── Dispatch to the active view ─────────────────────────────────────────────
if active_view == "dashboard":
    from views.dashboard import render as _render
elif active_view == "import":
    from views.import_data import render as _render
elif active_view == "sensors":
    from views.sensors import render as _render
elif active_view == "timeseries":
    from views.timeseries import render as _render
elif active_view == "correlation":
    from views.correlation import render as _render
elif active_view == "anomaly":
    from views.anomaly import render as _render
elif active_view == "trend":
    from views.trend import render as _render
elif active_view == "data_quality":
    from views.data_quality import render as _render
elif active_view == "data":
    from views.raw_sample import render as _render
elif active_view == "settings":
    from views.settings import render as _render
else:
    from views.dashboard import render as _render

_render()
