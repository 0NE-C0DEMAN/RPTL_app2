"""Overview view — institutional KPI strip + per-sensor-family panels.

Single-screen summary so the engineer can confirm at a glance:
* Dataset context (date span, sample rate, sensor count, type breakdown,
  data coverage) — KPI ribbon strip across the top.
* Per-sensor-family time-series overlay paired with a right-rail
  "print panel" showing the per-sensor min/max/drift/slope diagnostics.

Heavy work goes through ``lib.shm.load_dataset`` which is cached on
(table_name, version), so repeated visits cost nothing.
"""
from __future__ import annotations

import html as html_mod

import numpy as np
import pandas as pd
import streamlit as st

from lib.charts.canvas import chart_panel, icon_btn, series
from lib.components import (
    badge, empty_state, kpi_strip, page_header, print_panel, section_heading,
)
from lib.icons import svg
from lib.shm import (
    SENSOR_TYPES, classify_columns, color_for_sensor, get_active_dataset,
    sensor_stats, trend_slope,
)
from lib.state import get_active_info
from lib.timewindow import apply_time_window, time_window_bar


def render() -> None:
    info = get_active_info()
    if info is None:
        page_header("Overview", "Long-term sensor monitoring")
        empty_state(
            "database",
            "No active dataset",
            "Go to Import Data and load a file (or click Load Demo Dataset).",
        )
        return

    df_full = get_active_dataset()
    if df_full is None or df_full.empty:
        page_header("Overview", info.source_filename or info.table_name)
        empty_state("alert", "Couldn't load dataset",
                    "The active table is empty or the time column couldn't be parsed.")
        return

    # ── Hidden Export trigger — bridge clicks to download CSV ───────────
    csv_bytes = df_full.to_csv(index=True).encode("utf-8")
    st.download_button(
        "·", data=csv_bytes,
        file_name=f"{info.table_name}_overview.csv",
        mime="text/csv", key="__dash_export_csv",
    )

    span = _format_period(df_full.index)
    sensor_count = len(df_full.columns)
    type_map = classify_columns(list(df_full.columns))
    n_types = sum(1 for t in SENSOR_TYPES if type_map.get(t["id"]))

    right = (
        badge(f"{sensor_count} sensors", "blue")
        + badge(span, "gray")
        + '<button type="button" class="rgf-btn-sm" data-action="export-dashboard">'
        + f'{svg("download", size=13)} Export'
        + '</button>'
    )
    page_header(
        "Overview",
        f"{info.source_filename or info.table_name} · {info.row_count:,} samples",
        right_html=right,
    )

    # ── Global time-window filter ────────────────────────────────────────
    time_window_bar(df_full)
    df = apply_time_window(df_full)
    if df.empty:
        empty_state("ruler", "No samples in this window",
                    "Try a wider preset or 'All' to see data again.")
        return

    # ── KPI strip — institutional ribbon + 5-cell metric rail ───────────
    _render_kpi_strip(df, type_map, n_types)

    # ── Per-family panels: chart on the left, diagnostics rail right ────
    section_heading("Sensor families · time-series overview", major=True)
    for t in SENSOR_TYPES:
        cols_of_type = type_map.get(t["id"], [])
        if not cols_of_type:
            continue
        _render_family_row(df, t, cols_of_type)


# ── KPI strip ────────────────────────────────────────────────────────────────
def _render_kpi_strip(
    df: pd.DataFrame, type_map: dict, n_types: int,
) -> None:
    """5-cell KPI rail under a `Dataset Context` ribbon."""
    span_days = _span_days(df.index)
    sample_step = _median_step_minutes(df.index)
    overall_nan = float(df.isna().sum().sum() / max(df.size, 1))
    coverage_pct = (1.0 - overall_nan) * 100.0
    cov_signal = "pos" if coverage_pct >= 95 else ("warn" if coverage_pct >= 85 else "neg")

    type_breakdown_parts: list[str] = []
    for t in SENSOR_TYPES:
        c = len(type_map.get(t["id"], []))
        if c:
            type_breakdown_parts.append(f"{c}×{t['label'].split(' (')[0][:6]}")
    type_sub = " · ".join(type_breakdown_parts) or "—"

    if isinstance(df.index, pd.DatetimeIndex) and len(df.index):
        period_sub = f"{df.index[0]:%Y-%m-%d} → {df.index[-1]:%Y-%m-%d}"
    else:
        period_sub = f"{len(df.index):,} rows"

    kpi_strip(
        "Dataset context",
        [
            {
                "label": "Time Span",
                "value": _fmt_num(span_days, decimals=1),
                "unit": "days",
                "sub": period_sub,
                "lead": True,
            },
            {
                "label": "Sample Rate",
                "value": _fmt_step(sample_step),
                "sub": f"n = {len(df):,}",
            },
            {
                "label": "Sensors",
                "value": str(len(df.columns)),
                "unit": "channels",
                "sub": type_sub,
            },
            {
                "label": "Sensor Types",
                "value": str(n_types),
                "sub": "unique families",
            },
            {
                "label": "Data Coverage",
                "value": f"{coverage_pct:,.1f}",
                "unit": "%",
                "sub": f"NaN frac {overall_nan*100:.2f}%",
                "signal": cov_signal,
            },
        ],
    )


# ── Per-family row: chart + diagnostics rail ────────────────────────────────
def _render_family_row(
    df: pd.DataFrame, type_meta: dict, cols: list[str],
) -> None:
    """Two-column row — chart on the left, ip-wrap diagnostics on the right.

    The chart shows every sensor in this family overlaid (one distinct
    shade of the family's color). The right rail surfaces the most
    drifting / most variable channel as the hero highlight, then lists
    the per-sensor numeric summary as K/V rows.
    """
    # Slice + downsample for the chart — at 1 min × 31 days we have
    # 45k samples, more than the canvas needs. Pick at most ~2k.
    if len(df) > 2_000:
        idx = np.linspace(0, len(df) - 1, 2_000).astype(int)
        chart_df = df.iloc[idx]
    else:
        chart_df = df

    if isinstance(chart_df.index, pd.Timestamp.__mro__[0]):
        pass
    if isinstance(chart_df.index, pd.DatetimeIndex):
        t0 = chart_df.index[0]
        x = (chart_df.index - t0).total_seconds().to_numpy() / 86400.0
        x_label = f"Days from {t0:%Y-%m-%d}"
    else:
        x = np.asarray(chart_df.index, dtype=float)
        x_label = chart_df.index.name or "Time"

    df_cols = list(df.columns)
    series_list = [
        series(chart_df[c].to_numpy(dtype=float),
               color_for_sensor(c, df_cols), c, filled=False)
        for c in cols
    ]

    type_lbl = type_meta["label"].split(" (")[0]
    unit = type_meta["unit"]
    title = f"{type_meta['label']} · {len(cols)} channel{'s' if len(cols) > 1 else ''}"
    y_label = f"{type_lbl} ({unit})" if unit else type_lbl

    # Build per-sensor stats up front so we can pick a hero highlight.
    per_sensor: list[dict] = []
    for c in cols:
        s = sensor_stats(df[c])
        slope = trend_slope(df[c])
        per_sensor.append({
            "name":  c,
            "min":   s["min"],
            "max":   s["max"],
            "mean":  s["mean"],
            "std":   s["std"],
            "drift": s["drift"],
            "slope": slope,
            "nan":   s["nan_frac"],
        })
    # Sort by |drift| desc so the most-active channel is at the top.
    per_sensor.sort(key=lambda r: -abs(r["drift"] or 0.0))
    hero = per_sensor[0]
    hero_label = f"{hero['name']} · max |drift|"
    hero_value = f"{hero['drift']:+.4f} {unit}".strip()

    chart_col, rail_col = st.columns([2.4, 1], gap="medium")
    with chart_col:
        chart_panel(
            title, series_list, x_data=x,
            x_label=x_label,
            y_label=y_label,
            height=240,
            actions_html=icon_btn("download", title="Export"),
            key=f"shm_overview_{type_meta['id']}",
        )
    with rail_col:
        rows: list[tuple[str, str]] = []
        for r in per_sensor:
            sign = "+" if (r["slope"] or 0) >= 0 else ""
            rows.append((
                r["name"],
                f"min {_fmt_num(r['min'])}  max {_fmt_num(r['max'])}  "
                f"drift {sign}{_fmt_num(r['drift'])}",
            ))
        print_panel(
            f"{type_lbl} diagnostics",
            rows,
            status=f"{len(cols)} ch",
            hl_label=hero_label,
            hl_value=hero_value,
        )


# ── Small helpers ────────────────────────────────────────────────────────────
def _span_days(idx: pd.Index) -> float:
    if isinstance(idx, pd.DatetimeIndex) and len(idx) >= 2:
        return float((idx[-1] - idx[0]).total_seconds() / 86400.0)
    if len(idx) >= 2:
        try:
            return float(idx[-1] - idx[0]) / 86400.0
        except Exception:
            return float(len(idx))
    return 0.0


def _median_step_minutes(idx: pd.Index) -> float | None:
    """Median sample interval in minutes — None when not a DatetimeIndex."""
    if not isinstance(idx, pd.DatetimeIndex) or len(idx) < 2:
        return None
    diffs = (idx[1:] - idx[:-1]).total_seconds().to_numpy()
    if not len(diffs):
        return None
    return float(np.median(diffs)) / 60.0


def _fmt_step(minutes: float | None) -> str:
    if minutes is None:
        return "—"
    if minutes < 1:
        return f"{minutes*60:.1f} s"
    if minutes < 60:
        return f"{minutes:.1f} min"
    if minutes < 60 * 24:
        return f"{minutes/60:.1f} h"
    return f"{minutes/60/24:.1f} d"


def _format_period(idx: pd.Index) -> str:
    if isinstance(idx, pd.DatetimeIndex) and len(idx):
        return f"{idx[0]:%Y-%m-%d} → {idx[-1]:%Y-%m-%d}"
    return f"{len(idx):,} samples"


def _fmt_num(v, decimals: int = 3) -> str:
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
    return f"{f:,.{decimals}f}"
