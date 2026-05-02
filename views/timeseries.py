"""Time Series view — multi-sensor overlay with resampling.

Top: KPI strip of the current selection (sensors picked, period,
sample-rate after resample). Then a sidebar (sensor multi-select +
resample + aggregation) and the main overlay chart. Sensors of mixed
units (e.g. an LVDT in mm + a thermocouple in °C) auto-route to
left/right axes and the legend strip shows axis tags.
"""
from __future__ import annotations

import html as html_mod

import numpy as np
import pandas as pd
import streamlit as st

from lib.charts.canvas import chart_panel, icon_btn, series
from lib.components import (
    empty_state, kpi_strip, page_header, section_heading,
)
from lib.shm import (
    RESAMPLE_RULES, classify_columns, color_for_sensor, get_active_dataset,
    resampled_view, sensor_unit,
)
from lib.state import get_active_info
from lib.timewindow import apply_time_window, time_window_bar


_AGG_OPTIONS = ["mean", "min", "max", "std", "median"]


def render() -> None:
    info = get_active_info()
    if info is None:
        page_header("Time Series", "Multi-sensor overlay with resampling")
        empty_state("database", "No active dataset",
                    "Import a file to start exploring.")
        return

    df_full = get_active_dataset()
    if df_full is None or df_full.empty:
        page_header("Time Series", info.source_filename or info.table_name)
        empty_state("alert", "Couldn't load dataset", "")
        return

    page_header(
        "Time Series",
        "Overlay any combination of sensors — resample / aggregate over the period.",
    )

    time_window_bar(df_full)
    df = apply_time_window(df_full)
    if df.empty:
        empty_state("ruler", "No samples in this window",
                    "Try a wider preset to see data again.")
        return

    # ── Sidebar (sensor picker + resample) | Main (chart) ────────────────
    side_col, main_col = st.columns([1, 3.0], gap="medium")
    with side_col:
        picked = _render_sidebar(df)
    with main_col:
        _render_chart(df, picked)


# ── Sidebar — sensor picker + resample controls ─────────────────────────────
def _render_sidebar(df: pd.DataFrame) -> list[str]:
    ss = st.session_state
    cols = list(df.columns)

    # Default selection: first sensor of each type, up to 4 total
    if "shm_ts_sensors" not in ss or not ss["shm_ts_sensors"]:
        default = []
        type_map = classify_columns(cols)
        for tcols in type_map.values():
            if tcols:
                default.append(tcols[0])
            if len(default) >= 4:
                break
        ss["shm_ts_sensors"] = default

    ss.setdefault("shm_ts_resample", "raw")
    ss.setdefault("shm_ts_agg", "mean")

    with st.container(key="rgf_panel_ts_controls"):
        st.markdown(
            '<div class="rgf-panel-hdr"><span class="rgf-panel-title">'
            'Series</span></div>',
            unsafe_allow_html=True,
        )
        ss["shm_ts_sensors"] = st.multiselect(
            "Sensors", cols,
            default=[c for c in ss["shm_ts_sensors"] if c in cols],
            key="shm_ts_sensors_inp",
            label_visibility="collapsed",
        )
        st.markdown('<div class="rgf-cb-label">Resample</div>',
                    unsafe_allow_html=True)
        rules = list(RESAMPLE_RULES.keys())
        idx_r = rules.index(ss["shm_ts_resample"]) if ss["shm_ts_resample"] in rules else 0
        ss["shm_ts_resample"] = st.selectbox(
            "Resample", rules, index=idx_r,
            key="shm_ts_resample_inp", label_visibility="collapsed",
        )
        st.markdown('<div class="rgf-cb-label">Aggregation</div>',
                    unsafe_allow_html=True)
        idx_a = _AGG_OPTIONS.index(ss["shm_ts_agg"]) if ss["shm_ts_agg"] in _AGG_OPTIONS else 0
        ss["shm_ts_agg"] = st.selectbox(
            "Aggregation", _AGG_OPTIONS, index=idx_a,
            key="shm_ts_agg_inp", label_visibility="collapsed",
        )

    return ss["shm_ts_sensors"]


# ── Main chart ──────────────────────────────────────────────────────────────
def _render_chart(df: pd.DataFrame, picked: list[str]) -> None:
    if not picked:
        empty_state("ruler", "Pick one or more sensors",
                    "Use the multi-select on the left to choose channels.")
        return

    ss = st.session_state
    df_v = resampled_view(
        df[picked], rule=ss["shm_ts_resample"], agg=ss["shm_ts_agg"]
    )

    # Decide axes: each sensor unit gets its own axis. With 2+ unit
    # families, route the FIRST family to the left axis and the SECOND
    # family to the right axis. Anything beyond two families collapses
    # to right axis (rare in practice).
    units = {c: sensor_unit(c) for c in picked}
    family_left = next(iter(units.values()), "")
    df_cols = list(df.columns)
    series_list = []
    for c in picked:
        is_left = (units[c] == family_left)
        series_list.append(series(
            df_v[c].to_numpy(dtype=float),
            color_for_sensor(c, df_cols), c,
            axis="left" if is_left else "right",
            filled=False,
        ))

    # X axis — datetime index → days-since-start (float).
    if isinstance(df_v.index, pd.DatetimeIndex) and len(df_v.index):
        t0 = df_v.index[0]
        x = (df_v.index - t0).total_seconds().to_numpy() / 86400.0
        x_label = f"Days from {t0:%Y-%m-%d %H:%M}"
        period_str = f"{df_v.index[0]:%Y-%m-%d %H:%M} → {df_v.index[-1]:%Y-%m-%d %H:%M}"
    else:
        x = np.asarray(df_v.index, dtype=float)
        x_label = "Time"
        period_str = f"{len(df_v):,} rows"

    # Y labels — the unit of the first picked sensor on each side.
    y_left = family_left or "value"
    other_units = [u for u in units.values() if u != family_left]
    y_right = other_units[0] if other_units else ""

    # ── KPI strip — selection summary ────────────────────────────────────
    rows = len(df_v)
    rule = ss["shm_ts_resample"]
    if rule == "raw":
        rate_str = "raw cadence"
    else:
        rate_str = f"resampled · {rule}"
    n_left = sum(1 for u in units.values() if u == family_left)
    n_right = len(picked) - n_left
    axis_breakdown = (
        f"L:{n_left} ({y_left})  R:{n_right} ({y_right})"
        if n_right else f"L:{n_left} ({y_left})"
    )
    kpi_strip(
        "Active selection",
        [
            {
                "label": "Sensors",
                "value": str(len(picked)),
                "unit": "channels",
                "sub": axis_breakdown,
                "lead": True,
            },
            {
                "label": "Resample",
                "value": rule.upper() if rule != "raw" else "RAW",
                "sub": ss["shm_ts_agg"],
            },
            {
                "label": "Rows",
                "value": f"{rows:,}",
                "sub": rate_str,
            },
            {
                "label": "Period",
                "value": "—",
                "sub": period_str,
            },
        ],
    )

    section_heading("Overlay chart", major=True)
    chart_panel(
        f"{len(picked)} sensors · {rule} · {ss['shm_ts_agg']}",
        series_list,
        x_data=x,
        x_label=x_label,
        y_label=y_left,
        y_label_right=y_right,
        height=460,
        actions_html=icon_btn("download", title="Export"),
        key=f"shm_ts_{rule}_{ss['shm_ts_agg']}_"
            + "_".join(picked)[:80],
    )

    if y_right and y_left and y_right != y_left:
        st.markdown(
            f'<div class="rgf-shm-meta">'
            f'Mixed-unit overlay — channels with unit '
            f'<b>{html_mod.escape(y_left)}</b> on the LEFT axis, '
            f'<b>{html_mod.escape(y_right)}</b> on the RIGHT axis. '
            f'Legend chips show <code>↤L</code> / <code>↦R</code> '
            f'for axis routing.'
            f'</div>',
            unsafe_allow_html=True,
        )
