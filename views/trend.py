"""Trend / Drift view — daily aggregates + linear fit per sensor.

Top: KPI strip of dataset-level drift summary (steepest slope channel,
total drift across families, period). Then per-family rows: chart on
the left (daily mean line + min/max band + linear-fit overlay) paired
with a right-rail print_panel listing each sensor's slope, drift, and
fit quality.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from lib.charts.canvas import chart_panel, icon_btn, series
from lib.components import (
    empty_state, kpi_strip, page_header, print_panel, section_heading,
)
from lib.shm import (
    SENSOR_TYPES, classify_columns, color_for_sensor, get_active_dataset,
    sensor_unit, trend_slope,
)
from lib.shm.analyzer import daily_aggregates
from lib.state import get_active_info
from lib.timewindow import apply_time_window, time_window_bar


def render() -> None:
    info = get_active_info()
    if info is None:
        page_header("Trend / Drift", "Daily aggregates + linear-trend slope")
        empty_state("database", "No active dataset", "")
        return

    df_full = get_active_dataset()
    if df_full is None or df_full.empty:
        page_header("Trend / Drift", info.source_filename or info.table_name)
        empty_state("alert", "Couldn't load dataset", "")
        return

    page_header(
        "Trend / Drift",
        "Per-sensor daily mean (with min/max band) and linear-fit slope.",
    )

    time_window_bar(df_full)
    df = apply_time_window(df_full)
    if df.empty:
        empty_state("ruler", "No samples in this window",
                    "Try a wider preset to see data again.")
        return

    if not isinstance(df.index, pd.DatetimeIndex):
        empty_state("ruler", "Trend view needs datetime index",
                    "The Time column couldn't be parsed as timestamps.")
        return

    daily_mean = daily_aggregates(df, rule="daily", agg="mean")
    daily_min = daily_aggregates(df, rule="daily", agg="min")
    daily_max = daily_aggregates(df, rule="daily", agg="max")

    # Days since start for the x-axis
    t0 = daily_mean.index[0]
    x = (daily_mean.index - t0).total_seconds().to_numpy() / 86400.0
    x_label = f"Days from {t0:%Y-%m-%d}"

    # ── KPI strip — global drift summary ─────────────────────────────────
    _render_drift_strip(df, daily_mean, x)

    type_map = classify_columns(list(df.columns))
    df_cols = list(df.columns)
    for t in SENSOR_TYPES:
        cols_of_type = type_map.get(t["id"], [])
        if not cols_of_type:
            continue
        section_heading(
            f"{t['label']} · drift diagnostics",
            major=True,
        )
        _render_family_row(
            df, t, cols_of_type, daily_mean, daily_min, daily_max,
            x, x_label, df_cols,
        )


# ── Drift KPI strip ─────────────────────────────────────────────────────────
def _render_drift_strip(df: pd.DataFrame, daily_mean: pd.DataFrame, x: np.ndarray) -> None:
    """4 KPI cells summarising drift across all sensors."""
    slopes: dict[str, float] = {}
    abs_drifts: dict[str, float] = {}
    for c in df.columns:
        slopes[c] = trend_slope(df[c])
        s = df[c].dropna()
        if len(s) >= 2:
            abs_drifts[c] = float(s.iloc[-1] - s.iloc[0])
        else:
            abs_drifts[c] = 0.0

    if not slopes:
        return

    # Sensor with biggest |slope|
    steepest = max(slopes.items(), key=lambda kv: abs(kv[1]))
    biggest_drift = max(abs_drifts.items(), key=lambda kv: abs(kv[1]))
    n_days = float(x[-1] - x[0]) if len(x) >= 2 else 0.0

    # Signal: |slope| / |max drift| ratio — a steep slope on a thin
    # range is more concerning than a gentle slope on a thick range.
    steep_signal = (
        "neg" if abs(steepest[1]) >= 0.05
        else ("warn" if abs(steepest[1]) >= 0.005 else "pos")
    )

    kpi_strip(
        "Drift over period",
        [
            {
                "label": "Period",
                "value": f"{n_days:,.1f}",
                "unit": "days",
                "sub": f"{daily_mean.index[0]:%Y-%m-%d} → {daily_mean.index[-1]:%Y-%m-%d}",
                "lead": True,
            },
            {
                "label": "Daily Aggregates",
                "value": f"{len(daily_mean):,}",
                "unit": "rows",
                "sub": "mean · min · max",
            },
            {
                "label": "Steepest Slope",
                "value": steepest[0],
                "sub": f"{steepest[1]:+.5f} {sensor_unit(steepest[0])}/day".rstrip(),
                "signal": steep_signal,
            },
            {
                "label": "Biggest |Drift|",
                "value": biggest_drift[0],
                "sub": f"Δ {biggest_drift[1]:+.4f} {sensor_unit(biggest_drift[0])}".rstrip(),
            },
        ],
    )


# ── Per-family chart + diagnostics rail ─────────────────────────────────────
def _render_family_row(
    df: pd.DataFrame, type_meta: dict, cols: list[str],
    daily_mean: pd.DataFrame, daily_min: pd.DataFrame, daily_max: pd.DataFrame,
    x: np.ndarray, x_label: str, df_cols: list[str],
) -> None:
    """Two-column row: overlay chart left, print_panel diagnostics right.

    The chart overlays each channel's daily mean line; the rail shows
    a slope+drift K/V pair per sensor.
    """
    type_lbl = type_meta["label"].split(" (")[0]
    unit = type_meta["unit"]

    # Build series for every channel in this family. Daily MEAN gets
    # a solid filled line; we skip the min/max bands here for the
    # multi-channel overlay (they'd visually collide).
    series_list: list[dict] = []
    diagnostics: list[dict] = []
    for c in cols:
        color = color_for_sensor(c, df_cols)
        y_mean = daily_mean[c].to_numpy(dtype=float)
        slope = trend_slope(df[c])
        intercept = float(np.nanmean(y_mean) - slope * np.nanmean(x))
        trend_y = slope * x + intercept

        s_clean = df[c].dropna()
        drift = float(s_clean.iloc[-1] - s_clean.iloc[0]) if len(s_clean) >= 2 else 0.0

        series_list.append(series(y_mean, color, c, filled=False))
        # Trend line dashed in the same colour but darker / dotted.
        series_list.append(series(
            trend_y, color, f"_trend_{c}",
            dashed=True, filled=False,
        ))
        diagnostics.append({
            "name":  c,
            "slope": slope,
            "drift": drift,
            "color": color,
        })

    diagnostics.sort(key=lambda r: -abs(r["slope"]))
    hero = diagnostics[0]
    hero_value = f"{hero['slope']:+.5f} {unit}/day".rstrip()

    chart_col, rail_col = st.columns([2.4, 1], gap="medium")
    with chart_col:
        chart_panel(
            f"{type_lbl} · daily mean + linear fit",
            series_list,
            x_data=x,
            x_label=x_label,
            y_label=f"{type_lbl} ({unit})" if unit else type_lbl,
            height=240,
            actions_html=icon_btn("download", title="Export"),
            key=f"shm_trend_{type_meta['id']}",
        )
    with rail_col:
        rows: list[tuple[str, str]] = []
        for d in diagnostics:
            rows.append((
                d["name"],
                f"slope {d['slope']:+.5f}  drift {d['drift']:+.4f}",
            ))
        print_panel(
            f"{type_lbl} slopes",
            rows,
            status=f"{len(cols)} ch",
            hl_label=f"{hero['name']} · steepest",
            hl_value=hero_value,
        )
