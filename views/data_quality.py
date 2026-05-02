"""Data Quality view — per-sensor coverage Gantt + gap diagnostics.

SHM acquisition systems lose channels: a thermocouple wire breaks, a
DAQ reboots, a logger battery dies. The result is gaps in the time
series. This view makes those gaps visible at a glance:

* A KPI strip with the dataset-wide coverage stats.
* A Gantt-style coverage timeline — one row per sensor, green where
  the sample is non-NaN, red bars where it's missing. Engineers can
  see "ok LVDT4 had a 4-day outage Mar-15 to Mar-18" without scrolling
  through every chart.
* A right-rail print panel listing the worst offenders (sensor with
  longest gap, sensor with worst coverage, sensor with most gap
  episodes).
"""
from __future__ import annotations

import html as html_mod

import numpy as np
import pandas as pd
import streamlit as st

from lib.components import (
    empty_state, kpi_strip, page_header, print_panel, section_heading,
)
from lib.shm import (
    classify_columns, color_for_sensor, get_active_dataset, sensor_unit,
)
from lib.state import get_active_info
from lib.timewindow import apply_time_window, time_window_bar


# Threshold (in samples) below which a NaN run isn't called a "gap" — a
# stray missing sample isn't a sensor outage.
_MIN_GAP_SAMPLES = 3


def render() -> None:
    info = get_active_info()
    if info is None:
        page_header("Data Quality", "Coverage timeline + gap diagnostics")
        empty_state("database", "No active dataset", "")
        return

    df_full = get_active_dataset()
    if df_full is None or df_full.empty:
        page_header("Data Quality", info.source_filename or info.table_name)
        empty_state("alert", "Couldn't load dataset", "")
        return

    page_header(
        "Data Quality",
        "Per-sensor coverage timeline. Red = data missing, green = "
        "sample present. Identify outages at a glance.",
    )

    time_window_bar(df_full)
    df = apply_time_window(df_full)
    if df.empty:
        empty_state("ruler", "No samples in this window",
                    "Try a wider preset to see data again.")
        return

    if not isinstance(df.index, pd.DatetimeIndex) or len(df) < 2:
        empty_state(
            "ruler", "Coverage view needs a datetime index",
            "The Time column couldn't be parsed as timestamps, "
            "so we can't plot per-sensor coverage over time.",
        )
        return

    # Per-sensor gap analysis
    diags = _per_sensor_diagnostics(df)
    if not diags:
        empty_state("ruler", "No sensors", "")
        return

    # KPI strip — dataset-wide quality summary
    _render_quality_kpi(df, diags)

    # Coverage Gantt
    section_heading("Coverage timeline · per sensor", major=True)
    chart_col, rail_col = st.columns([2.4, 1], gap="medium")
    with chart_col:
        _render_gantt(df, diags)
    with rail_col:
        _render_offenders_panel(diags)


# ── Diagnostics ─────────────────────────────────────────────────────────────
def _per_sensor_diagnostics(df: pd.DataFrame) -> list[dict]:
    """Compute coverage stats + gap segments for every sensor.

    Returns a list of dicts (one per sensor) with:
        ``name``           — column name
        ``coverage``       — fraction of non-NaN samples (0.0–1.0)
        ``gap_segments``   — list of (start_idx, end_idx) tuples
        ``longest_gap_n``  — length in samples of the longest gap
        ``longest_gap_dt`` — duration of the longest gap (Timedelta)
        ``longest_gap_at`` — Timestamp where the longest gap begins
        ``n_episodes``     — number of distinct gap episodes
        ``unit``           — sensor unit string (mm / ° / °C / …)
    """
    out: list[dict] = []
    for c in df.columns:
        s = df[c]
        is_na = s.isna().to_numpy()
        n = len(is_na)
        if n == 0:
            continue
        coverage = float(1.0 - is_na.mean())

        # Find runs of NaN >= _MIN_GAP_SAMPLES
        segments: list[tuple[int, int]] = []
        i = 0
        while i < n:
            if is_na[i]:
                j = i
                while j < n and is_na[j]:
                    j += 1
                if j - i >= _MIN_GAP_SAMPLES:
                    segments.append((i, j - 1))
                i = j
            else:
                i += 1

        longest_n = 0
        longest_at = None
        longest_dt = pd.Timedelta(0)
        for (a, b) in segments:
            ln = b - a + 1
            if ln > longest_n:
                longest_n = ln
                longest_at = df.index[a]
                longest_dt = df.index[b] - df.index[a] if b > a else pd.Timedelta(0)

        out.append({
            "name":           c,
            "coverage":       coverage,
            "gap_segments":   segments,
            "longest_gap_n":  longest_n,
            "longest_gap_dt": longest_dt,
            "longest_gap_at": longest_at,
            "n_episodes":     len(segments),
            "unit":           sensor_unit(c),
        })
    return out


# ── KPI strip ───────────────────────────────────────────────────────────────
def _render_quality_kpi(df: pd.DataFrame, diags: list[dict]) -> None:
    avg_cov = float(np.mean([d["coverage"] for d in diags])) * 100.0
    cov_signal = "pos" if avg_cov >= 95 else ("warn" if avg_cov >= 85 else "neg")

    worst_cov = min(diags, key=lambda d: d["coverage"])
    longest = max(diags, key=lambda d: d["longest_gap_n"])
    most_eps = max(diags, key=lambda d: d["n_episodes"])
    n_total_gaps = sum(d["n_episodes"] for d in diags)

    longest_dt_str = _fmt_timedelta(longest["longest_gap_dt"])
    period_str = (f"{df.index[0]:%Y-%m-%d %H:%M} → "
                  f"{df.index[-1]:%Y-%m-%d %H:%M}")

    kpi_strip(
        "Coverage summary",
        [
            {
                "label": "Avg Coverage",
                "value": f"{avg_cov:,.1f}",
                "unit": "%",
                "sub": period_str,
                "lead": True,
                "signal": cov_signal,
            },
            {
                "label": "Lowest Coverage",
                "value": worst_cov["name"],
                "sub": f"{worst_cov['coverage']*100:,.1f}% non-NaN",
                "signal": "neg" if worst_cov["coverage"] < 0.85 else (
                    "warn" if worst_cov["coverage"] < 0.95 else None),
            },
            {
                "label": "Longest Gap",
                "value": longest_dt_str,
                "sub": f"{longest['name']} · {longest['longest_gap_n']:,} samples",
                "signal": "warn" if longest["longest_gap_n"] > 0 else None,
            },
            {
                "label": "Total Gap Episodes",
                "value": f"{n_total_gaps:,}",
                "sub": f"≥ {_MIN_GAP_SAMPLES} samples each",
            },
            {
                "label": "Most Episodes",
                "value": most_eps["name"],
                "sub": f"{most_eps['n_episodes']:,} outages",
            },
        ],
    )


# ── Coverage Gantt ──────────────────────────────────────────────────────────
def _render_gantt(df: pd.DataFrame, diags: list[dict]) -> None:
    """One bar per sensor — full-width green base, red overlays where
    the sensor was offline.

    Implementation is plain HTML/CSS positioning via percentages so we
    don't need a charting library for this — and engineers can see the
    timeline without an iframe round-trip.
    """
    type_map = classify_columns(list(df.columns))
    df_cols = list(df.columns)
    t0 = df.index[0]
    span = (df.index[-1] - t0).total_seconds()
    if span <= 0:
        empty_state("ruler", "Window too narrow",
                    "Pick a wider time range to see the timeline.")
        return

    rows_html: list[str] = []
    for c in df_cols:
        d = next((x for x in diags if x["name"] == c), None)
        if d is None:
            continue
        color = color_for_sensor(c, df_cols)
        cov_pct = d["coverage"] * 100.0
        cov_class = (
            "rgf-dq-cov-good" if d["coverage"] >= 0.95
            else ("rgf-dq-cov-warn" if d["coverage"] >= 0.85 else "rgf-dq-cov-bad")
        )
        # Gap overlays as % of the bar width
        overlays = []
        for (a, b) in d["gap_segments"]:
            x0 = (df.index[a] - t0).total_seconds() / span * 100.0
            x1 = (df.index[b] - t0).total_seconds() / span * 100.0
            w = max(0.2, x1 - x0)  # min 0.2% so single-sample-burst gaps stay visible
            tip = (
                f"{df.index[a]:%Y-%m-%d %H:%M} → "
                f"{df.index[b]:%Y-%m-%d %H:%M} "
                f"({_fmt_timedelta(df.index[b] - df.index[a])})"
            )
            overlays.append(
                f'<span class="rgf-dq-gap" '
                f'style="left:{x0:.3f}%; width:{w:.3f}%;" '
                f'title="{html_mod.escape(tip)}"></span>'
            )

        rows_html.append(
            f'<div class="rgf-dq-row">'
            f'<span class="rgf-dq-name" style="border-left-color:{color}">'
            f'{html_mod.escape(c)}</span>'
            f'<div class="rgf-dq-bar">'
            f'<div class="rgf-dq-fill"></div>'
            f'{"".join(overlays)}'
            f'</div>'
            f'<span class="rgf-dq-cov {cov_class}">{cov_pct:,.1f}%</span>'
            f'<span class="rgf-dq-eps">{d["n_episodes"]} ep</span>'
            f'</div>'
        )

    # Top axis ticks: 5 evenly-spaced timestamps
    n_ticks = 5
    ticks_html = "".join(
        f'<span class="rgf-dq-tick" style="left:{i/(n_ticks-1)*100:.2f}%">'
        f'{(t0 + (df.index[-1] - t0) * i / (n_ticks-1)):%m-%d}'
        f'</span>'
        for i in range(n_ticks)
    )

    with st.container(key="rgf_panel_dq_gantt"):
        st.markdown(
            '<div class="rgf-panel-hdr"><span class="rgf-panel-title">'
            f'Coverage · {len(diags)} sensors</span></div>'
            f'<div class="rgf-dq-axis"><span class="rgf-dq-axis-spacer"></span>'
            f'<div class="rgf-dq-axis-row">{ticks_html}</div></div>'
            f'<div class="rgf-dq-rows">{"".join(rows_html)}</div>'
            '<div class="rgf-dq-legend">'
            '<span><span class="rgf-dq-key rgf-dq-key-fill"></span> covered</span>'
            '<span><span class="rgf-dq-key rgf-dq-key-gap"></span> gap '
            f'(≥ {_MIN_GAP_SAMPLES} consecutive samples)</span>'
            '</div>',
            unsafe_allow_html=True,
        )


# ── Right rail: worst-offenders print panel ─────────────────────────────────
def _render_offenders_panel(diags: list[dict]) -> None:
    by_longest = sorted(diags, key=lambda d: -d["longest_gap_n"])[:5]
    hero = by_longest[0]
    hero_label = f"{hero['name']} · longest gap"
    hero_value = (_fmt_timedelta(hero["longest_gap_dt"])
                  + f" · {hero['longest_gap_n']:,} samples")

    rows: list[tuple[str, str]] = []
    for d in by_longest:
        if d["longest_gap_n"] == 0:
            rows.append((d["name"], "no gaps"))
        else:
            rows.append((
                d["name"],
                f"{_fmt_timedelta(d['longest_gap_dt'])} · "
                f"{d['n_episodes']} ep · {d['coverage']*100:,.1f}%",
            ))
    print_panel(
        "Worst offenders",
        rows,
        status=f"{len([d for d in diags if d['n_episodes']])} sensors w/ gaps",
        hl_label=hero_label,
        hl_value=hero_value,
    )


# ── Helpers ─────────────────────────────────────────────────────────────────
def _fmt_timedelta(td: pd.Timedelta) -> str:
    """Compact human-friendly duration: '4h 12m', '2d 3h', '23m', '45s'."""
    if pd.isna(td) or td.total_seconds() <= 0:
        return "—"
    secs = int(td.total_seconds())
    if secs < 60:
        return f"{secs}s"
    mins, s = divmod(secs, 60)
    if mins < 60:
        return f"{mins}m" if not s else f"{mins}m {s}s"
    hrs, m = divmod(mins, 60)
    if hrs < 24:
        return f"{hrs}h" if not m else f"{hrs}h {m}m"
    days, h = divmod(hrs, 24)
    return f"{days}d" if not h else f"{days}d {h}h"
