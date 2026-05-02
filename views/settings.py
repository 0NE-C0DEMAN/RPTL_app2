"""Settings — minimal SHM-side defaults.

Just the knobs that actually drive analytics:
* Default resample rule + aggregation (used by Time Series view)
* Default rolling-window + sigma threshold (used by Anomaly view)
"""
from __future__ import annotations

import html as html_mod
from contextlib import contextmanager

import streamlit as st

from lib.components import page_header
from lib.shm import RESAMPLE_RULES


_DEFAULTS = {
    "settings_default_resample": "raw",
    "settings_default_agg":      "mean",
    "settings_default_window":   60,
    "settings_default_sigma":    3.0,
}


def render() -> None:
    ss = st.session_state
    for k, v in _DEFAULTS.items():
        ss.setdefault(k, v)

    if st.button("·", key="__settings_save"):
        st.toast("Settings saved", icon=":material/check_circle:")
    if st.button("·", key="__settings_reset"):
        for k, v in _DEFAULTS.items():
            ss[k] = v
        st.toast("Settings reset to defaults", icon=":material/restart_alt:")
        st.rerun()

    page_header(
        "Settings",
        "Defaults for the Time Series + Anomaly views.",
    )

    col1, col2 = st.columns(2, gap="medium")
    with col1:
        with _panel("Resample Defaults"):
            _select("Resample rule", "settings_default_resample",
                    list(RESAMPLE_RULES.keys()))
            _select("Aggregation", "settings_default_agg",
                    ["mean", "min", "max", "std", "median"])
    with col2:
        with _panel("Anomaly Detection Defaults"):
            _number("Rolling window (samples)", "settings_default_window",
                    min_value=5, max_value=10_000, step=5)
            _number_float("Sigma threshold", "settings_default_sigma",
                          min_value=1.0, max_value=10.0, step=0.5)

    st.markdown(
        '<div class="rgf-settings-footer">'
        '<button type="button" class="rgf-btn-sm" '
        'data-action="settings-reset">Reset to Defaults</button>'
        '<button type="button" class="rgf-btn-save" '
        'data-action="settings-save">Save Settings</button>'
        '</div>',
        unsafe_allow_html=True,
    )


# ── Panel + field helpers ───────────────────────────────────────────────────
_PANEL_COUNTER = {"n": 0}


def _slug(title: str) -> str:
    return (
        title.lower()
             .replace("&", "and")
             .replace(" ", "_")
             .replace("-", "_")
    )


@contextmanager
def _panel(title: str):
    _PANEL_COUNTER["n"] += 1
    key = f"rgf_set_pnl_{_slug(title)}_{_PANEL_COUNTER['n']}"
    c = st.container(key=key)
    with c:
        st.markdown(
            f'<div class="rgf-settings-panel-hdr">{html_mod.escape(title)}</div>',
            unsafe_allow_html=True,
        )
        yield


def _label(text: str) -> None:
    st.markdown(
        f'<div class="rgf-settings-label">{html_mod.escape(text)}</div>',
        unsafe_allow_html=True,
    )


def _select(label: str, key: str, options: list[str]) -> None:
    _label(label)
    cur = st.session_state.get(key, options[0])
    idx = options.index(cur) if cur in options else 0
    st.session_state[key] = st.selectbox(
        label, options, index=idx,
        label_visibility="collapsed", key=f"{key}_inp",
    )


def _number(label: str, key: str, *, min_value: int, max_value: int, step: int = 1) -> None:
    _label(label)
    try:
        cur = int(st.session_state.get(key, min_value))
    except (TypeError, ValueError):
        cur = min_value
    cur = max(min_value, min(max_value, cur))
    st.session_state[key] = st.number_input(
        label, value=cur,
        min_value=min_value, max_value=max_value, step=step,
        label_visibility="collapsed", key=f"{key}_inp",
    )


def _number_float(label: str, key: str, *,
                  min_value: float, max_value: float, step: float = 0.5) -> None:
    _label(label)
    try:
        cur = float(st.session_state.get(key, min_value))
    except (TypeError, ValueError):
        cur = min_value
    cur = max(min_value, min(max_value, cur))
    st.session_state[key] = st.number_input(
        label, value=cur,
        min_value=min_value, max_value=max_value, step=step, format="%.2f",
        label_visibility="collapsed", key=f"{key}_inp",
    )
