"""lib/timewindow.py — global time-window filter + UI bar.

A single shared time window scopes every data view (Overview, Sensor
Browser, Time Series, Anomaly, Trend, Correlation, Data Quality). The
engineer picks a preset (24h / 7d / 30d / All) or a custom range; every
KPI strip and chart re-renders against the slice without a page reload.

State (in ``st.session_state``):
    ``rgf_tw_preset``   — one of {"24h", "7d", "30d", "all", "custom"}
    ``rgf_tw_from``     — pd.Timestamp anchoring custom-mode start
    ``rgf_tw_to``       — pd.Timestamp anchoring custom-mode end

Public:
    ``apply_time_window(df) -> pd.DataFrame``  — slice df by current window
    ``current_window_label() -> str``          — human-readable label
    ``time_window_bar(df_full)``               — render the preset bar UI
    ``window_bounds(df_full) -> (from, to)``   — resolved bounds for current preset
"""
from __future__ import annotations

from typing import Tuple

import pandas as pd
import streamlit as st


_KEY_PRESET = "rgf_tw_preset"
_KEY_FROM   = "rgf_tw_from"
_KEY_TO     = "rgf_tw_to"

_DEFAULT_PRESET = "all"

# Map of preset id → (label, lookback timedelta or None for "all")
PRESETS: list[tuple[str, str, pd.Timedelta | None]] = [
    ("24h", "Last 24h",  pd.Timedelta(hours=24)),
    ("7d",  "Last 7d",   pd.Timedelta(days=7)),
    ("30d", "Last 30d",  pd.Timedelta(days=30)),
    ("all", "All",       None),
]


def _ss():
    return st.session_state


def _ensure_state() -> None:
    if _KEY_PRESET not in _ss():
        _ss()[_KEY_PRESET] = _DEFAULT_PRESET


def current_preset() -> str:
    _ensure_state()
    return _ss()[_KEY_PRESET]


def set_preset(preset_id: str) -> None:
    _ss()[_KEY_PRESET] = preset_id


def window_bounds(df_full: pd.DataFrame) -> Tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Return ``(from, to)`` timestamps for the current preset.

    Anchored to ``df_full.index[-1]`` (the latest sample) for relative
    presets so the user sees "the last 7 days OF THIS DATASET" rather
    than "the last 7 days of wall-clock time" — matters for retrospective
    SHM analysis where the dataset may be months old.

    Returns ``(None, None)`` when the dataset has no datetime index or
    the preset is "all".
    """
    _ensure_state()
    if not isinstance(df_full.index, pd.DatetimeIndex) or df_full.empty:
        return None, None

    preset = _ss()[_KEY_PRESET]
    end_ts = df_full.index[-1]

    if preset == "all":
        return df_full.index[0], end_ts
    if preset == "custom":
        f = _ss().get(_KEY_FROM)
        t = _ss().get(_KEY_TO)
        # Coerce to Timestamps; fall through to "all" on bad inputs.
        try:
            f = pd.Timestamp(f) if f is not None else df_full.index[0]
            t = pd.Timestamp(t) if t is not None else end_ts
        except (TypeError, ValueError):
            return df_full.index[0], end_ts
        return f, t
    # Lookback presets
    for pid, _label, td in PRESETS:
        if pid == preset and td is not None:
            return max(df_full.index[0], end_ts - td), end_ts
    # Unknown preset → all
    return df_full.index[0], end_ts


def apply_time_window(df: pd.DataFrame, *, df_full: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return a slice of ``df`` restricted to the current time window.

    ``df_full`` is the unfiltered dataset used to anchor relative
    presets; defaults to ``df`` itself, which is correct when callers
    pass the full dataset (the common case in views that fetch via
    ``get_active_dataset()``).
    """
    if df is None or df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return df
    f, t = window_bounds(df_full if df_full is not None else df)
    if f is None or t is None:
        return df
    if current_preset() == "all":
        return df
    return df.loc[(df.index >= f) & (df.index <= t)]


def current_window_label(df_full: pd.DataFrame | None = None) -> str:
    """Human-readable summary of the active window — for KPI sub-lines."""
    _ensure_state()
    preset = _ss()[_KEY_PRESET]
    if preset == "all":
        return "All data"
    for pid, lbl, _ in PRESETS:
        if pid == preset:
            return lbl
    if preset == "custom" and df_full is not None and not df_full.empty:
        f, t = window_bounds(df_full)
        if f is not None and t is not None:
            return f"{f:%Y-%m-%d %H:%M} → {t:%Y-%m-%d %H:%M}"
    return "All data"


def time_window_bar(df_full: pd.DataFrame) -> None:
    """Render the time-window control bar.

    A horizontal strip with 4 preset buttons (24h / 7d / 30d / All)
    plus a "Custom…" expander that exposes from/to date pickers. The
    active preset gets accent styling; clicking any preset triggers a
    rerun so every chart below reflects the new slice.

    Skips silently when the dataset has no datetime index — some
    sources (counter-indexed acquisition dumps) just don't have time
    semantics, so the filter wouldn't make sense.
    """
    if not isinstance(df_full.index, pd.DatetimeIndex) or df_full.empty:
        return

    _ensure_state()
    active = _ss()[_KEY_PRESET]

    # Hidden trigger buttons — one per preset (+ custom). The visible
    # HTML pills below dispatch via the JS bridge (data-tw="<id>").
    for pid, _label, _td in PRESETS:
        if st.button("·", key=f"__tw_{pid}"):
            _ss()[_KEY_PRESET] = pid
            st.rerun()
    if st.button("·", key="__tw_custom"):
        _ss()[_KEY_PRESET] = "custom"
        st.rerun()

    f, t = window_bounds(df_full)
    f_str = f"{f:%Y-%m-%d %H:%M}" if f is not None else "—"
    t_str = f"{t:%Y-%m-%d %H:%M}" if t is not None else "—"

    pills_html = "".join(
        f'<button type="button" '
        f'class="rgf-tw-pill{" active" if pid == active else ""}" '
        f'data-tw="{pid}">'
        f'{label}'
        f'</button>'
        for pid, label, _ in PRESETS
    )
    pills_html += (
        f'<button type="button" '
        f'class="rgf-tw-pill{" active" if active == "custom" else ""}" '
        f'data-tw="custom">Custom…</button>'
    )

    # Sample count after window
    win_df = apply_time_window(df_full)
    n_in_window = len(win_df)
    n_total = len(df_full)
    cov_pct = (n_in_window / max(1, n_total)) * 100.0

    st.markdown(
        f'<div class="rgf-tw-bar">'
        f'<span class="rgf-tw-label">Time window</span>'
        f'<div class="rgf-tw-pills">{pills_html}</div>'
        f'<span class="rgf-tw-range">'
        f'<code>{f_str}</code> → <code>{t_str}</code>'
        f'</span>'
        f'<span class="rgf-tw-count">'
        f'{n_in_window:,} / {n_total:,} samples '
        f'<span class="rgf-tw-pct">({cov_pct:.0f}%)</span>'
        f'</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Custom-range date inputs (only shown when the user clicks Custom)
    if active == "custom":
        with st.expander("Custom range", expanded=True):
            full_lo = df_full.index[0].to_pydatetime()
            full_hi = df_full.index[-1].to_pydatetime()
            cf, ct = st.columns(2)
            with cf:
                new_from = st.date_input(
                    "From",
                    value=_ss().get(_KEY_FROM, full_lo).date()
                          if hasattr(_ss().get(_KEY_FROM, full_lo), "date")
                          else full_lo.date(),
                    min_value=full_lo.date(),
                    max_value=full_hi.date(),
                    key="rgf_tw_from_inp",
                )
            with ct:
                new_to = st.date_input(
                    "To",
                    value=_ss().get(_KEY_TO, full_hi).date()
                          if hasattr(_ss().get(_KEY_TO, full_hi), "date")
                          else full_hi.date(),
                    min_value=full_lo.date(),
                    max_value=full_hi.date(),
                    key="rgf_tw_to_inp",
                )
            _ss()[_KEY_FROM] = pd.Timestamp(new_from)
            _ss()[_KEY_TO] = pd.Timestamp(new_to) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
