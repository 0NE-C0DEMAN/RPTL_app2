"""Sensor Browser — one panel per sensor, grouped by type.

Each panel shows the sensor's full-period time series and a row of
mini stat chips (min · max · μ · σ · drift · slope · coverage). Sensors
are grouped by sensor-type family with a section heading per group.
Long files (45k+ rows) are downsampled to ~1500 points before
rendering.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from lib.charts.canvas import chart_panel, icon_btn, series
from lib.components import (
    empty_state, kpi_strip, page_header, section_heading, stat_mini,
)
from lib.shm import (
    SENSOR_TYPES, classify_columns, color_for_sensor, get_active_dataset,
    sensor_stats, sensor_unit, trend_slope,
)
from lib.state import get_active_info
from lib.timewindow import apply_time_window, time_window_bar


def render() -> None:
    info = get_active_info()
    if info is None:
        page_header("Sensor Browser", "Per-sensor time series + statistics")
        empty_state("database", "No active dataset",
                    "Import a file to start.")
        return

    df_full = get_active_dataset()
    if df_full is None or df_full.empty:
        page_header("Sensor Browser", info.source_filename or info.table_name)
        empty_state("alert", "Couldn't load dataset", "")
        return

    page_header(
        "Sensor Browser",
        f"{len(df_full.columns)} sensors · {len(df_full):,} samples · grouped by type",
    )

    time_window_bar(df_full)
    df = apply_time_window(df_full)
    if df.empty:
        empty_state("ruler", "No samples in this window",
                    "Try a wider preset to see data again.")
        return

    type_map = classify_columns(list(df.columns))

    # ── KPI strip — global health summary ────────────────────────────────
    _render_health_strip(df, type_map)

    # Pre-compute a single downsampled time axis (all sensors share it)
    if isinstance(df.index, pd.DatetimeIndex) and len(df.index):
        t_full = (df.index - df.index[0]).total_seconds().to_numpy() / 86400.0
        x_label = f"Days from {df.index[0]:%Y-%m-%d}"
    else:
        t_full = np.asarray(df.index, dtype=float)
        x_label = "Time"

    if len(df) > 1500:
        idx = np.linspace(0, len(df) - 1, 1500).astype(int)
    else:
        idx = np.arange(len(df))
    t_ds = t_full[idx]

    for t in SENSOR_TYPES:
        cols_of_type = type_map.get(t["id"], [])
        if not cols_of_type:
            continue
        section_heading(
            f"{t['label']} · {len(cols_of_type)} channels",
            major=True,
        )
        # 2 charts per row
        for i in range(0, len(cols_of_type), 2):
            row = cols_of_type[i:i + 2]
            cols_layout = st.columns(
                2 if len(row) == 2 else 1, gap="medium",
            )
            for j, c in enumerate(row):
                with cols_layout[j]:
                    _render_sensor_panel(df, c, t, idx, t_ds, x_label)


# ── Health strip — Total channels · Most-drifted · Lowest-coverage ──────────
def _render_health_strip(df: pd.DataFrame, type_map: dict) -> None:
    """Five KPI cells summarising sensor health across the whole dataset.

    Picks out the most "interesting" channel for each metric so the
    engineer can immediately tell which sensor needs attention without
    scrolling through every panel below.
    """
    # Most-drifted: largest |last - first|
    drifts: dict[str, float] = {}
    coverages: dict[str, float] = {}
    sigmas: dict[str, float] = {}
    for c in df.columns:
        s = sensor_stats(df[c])
        drifts[c] = abs(s["drift"]) if pd.notna(s["drift"]) else 0.0
        coverages[c] = 1.0 - s["nan_frac"]
        sigmas[c] = s["std"] if pd.notna(s["std"]) else 0.0
    most_drifted = max(drifts.items(), key=lambda kv: kv[1]) if drifts else ("—", 0.0)
    least_covered = min(coverages.items(), key=lambda kv: kv[1]) if coverages else ("—", 1.0)
    most_volatile = max(sigmas.items(), key=lambda kv: kv[1]) if sigmas else ("—", 0.0)

    avg_cov = float(np.mean(list(coverages.values()))) * 100.0 if coverages else 0.0
    cov_signal = "pos" if avg_cov >= 95 else ("warn" if avg_cov >= 85 else "neg")

    type_count = sum(1 for t in SENSOR_TYPES if type_map.get(t["id"]))

    kpi_strip(
        "Sensor health",
        [
            {
                "label": "Channels",
                "value": str(len(df.columns)),
                "unit": "total",
                "sub": f"{type_count} families",
                "lead": True,
            },
            {
                "label": "Avg Coverage",
                "value": f"{avg_cov:,.1f}",
                "unit": "%",
                "sub": "non-NaN samples",
                "signal": cov_signal,
            },
            {
                "label": "Most Drifted",
                "value": most_drifted[0],
                "sub": f"|drift| = {most_drifted[1]:,.4f} {sensor_unit(most_drifted[0])}".rstrip(),
            },
            {
                "label": "Most Volatile",
                "value": most_volatile[0],
                "sub": f"σ = {most_volatile[1]:,.4f} {sensor_unit(most_volatile[0])}".rstrip(),
            },
            {
                "label": "Lowest Coverage",
                "value": least_covered[0],
                "sub": f"{least_covered[1]*100:,.1f}%",
                "signal": "warn" if least_covered[1] < 0.95 else None,
            },
        ],
    )


# ── Per-sensor panel: chart + mini-stat grid ────────────────────────────────
def _render_sensor_panel(
    df: pd.DataFrame, col: str, type_meta: dict,
    idx: np.ndarray, t_ds: np.ndarray, x_label: str,
) -> None:
    """One sensor panel: time-series chart + 7-cell stat-mini grid."""
    s_full = df[col]
    y_ds = s_full.iloc[idx].to_numpy(dtype=float)
    color = color_for_sensor(col, list(df.columns))
    unit = sensor_unit(col) or type_meta["unit"]
    type_lbl = type_meta["label"].split(" (")[0]

    chart_panel(
        col,
        [series(y_ds, color, col, filled=True)],
        x_data=t_ds,
        x_label=x_label,
        y_label=f"{type_lbl} ({unit})" if unit else type_lbl,
        height=200,
        actions_html=icon_btn("download", title="Export"),
        key=f"shm_sensor_{col}",
    )

    s = sensor_stats(s_full)
    slope = trend_slope(s_full)
    coverage = (1.0 - s["nan_frac"]) * 100.0
    chips_html = "".join([
        stat_mini("Min",      _fmt(s["min"]),  unit),
        stat_mini("Max",      _fmt(s["max"]),  unit),
        stat_mini("Mean",     _fmt(s["mean"]), unit),
        stat_mini("σ",        _fmt(s["std"]),  unit),
        stat_mini("Drift",    _fmt(s["drift"]), unit),
        stat_mini("Slope",    _fmt(slope, 4), f"{unit}/d" if unit else "/d"),
        stat_mini("Coverage", f"{coverage:,.1f}", "%"),
    ])
    st.markdown(
        f'<div class="rgf-stat-mini-grid">{chips_html}</div>',
        unsafe_allow_html=True,
    )


def _fmt(v, decimals: int = 3) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    if not np.isfinite(f):
        return "—"
    if f == 0:
        return "0"
    ab = abs(f)
    if ab >= 1e6 or ab < 1e-4:
        return f"{f:.3g}"
    return f"{f:.{decimals}f}"
