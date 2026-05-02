"""Anomaly view — flag samples outside a rolling Nσ window.

Top: KPI strip summarising the detection (n flagged, anomaly rate,
worst excursion, parameters). Then a sidebar of controls (sensor /
window / sigma) next to a chart that overlays anomaly points as red
scatter, plus a right-rail print panel listing the first flagged
timestamps for inspection.
"""
from __future__ import annotations

import html as html_mod

import numpy as np
import pandas as pd
import streamlit as st

from lib.charts.canvas import chart_panel, icon_btn, series, series_xy
from lib.components import (
    empty_state, kpi_strip, page_header, print_panel, section_heading,
)
from lib.shm import (
    classify_columns, color_for_sensor, get_active_dataset,
    rolling_anomalies, sensor_label, sensor_unit,
)
from lib.state import get_active_info
from lib.timewindow import apply_time_window, time_window_bar


def render() -> None:
    info = get_active_info()
    if info is None:
        page_header("Anomaly Detection", "Rolling-σ outlier flagging")
        empty_state("database", "No active dataset", "")
        return

    df_full = get_active_dataset()
    if df_full is None or df_full.empty:
        page_header("Anomaly Detection", info.source_filename or info.table_name)
        empty_state("alert", "Couldn't load dataset", "")
        return

    page_header(
        "Anomaly Detection",
        "Samples that exceed mean ± Nσ of a rolling window. "
        "Adjust window + sigma in the sidebar.",
    )

    time_window_bar(df_full)
    df = apply_time_window(df_full)
    if df.empty:
        empty_state("ruler", "No samples in this window",
                    "Try a wider preset to see data again.")
        return

    cols = list(df.columns)
    ss = st.session_state
    type_map = classify_columns(cols)
    default = next((tcols[0] for tcols in type_map.values() if tcols), cols[0])
    ss.setdefault("shm_an_sensor", default)
    ss.setdefault("shm_an_window", 60)
    ss.setdefault("shm_an_sigma", 3.0)

    # Detection runs once; results feed both the KPI strip and the chart.
    s = df[ss["shm_an_sensor"]].astype(float)
    flags = rolling_anomalies(
        s, window=int(ss["shm_an_window"]), sigma=float(ss["shm_an_sigma"]),
    )
    n_valid = int(s.notna().sum())
    n_anoms = int(flags.sum())
    rate = n_anoms / max(1, n_valid)
    rate_signal = "neg" if rate >= 0.05 else ("warn" if rate >= 0.01 else "pos")
    worst_idx, worst_dev = _worst_excursion(s, flags)
    unit = sensor_unit(ss["shm_an_sensor"])

    kpi_strip(
        "Detection summary",
        [
            {
                "label": "Sensor",
                "value": ss["shm_an_sensor"],
                "sub": sensor_label(ss["shm_an_sensor"]),
                "lead": True,
            },
            {
                "label": "Anomalies Flagged",
                "value": f"{n_anoms:,}",
                "sub": f"of {n_valid:,} valid",
                "signal": rate_signal,
            },
            {
                "label": "Anomaly Rate",
                "value": f"{rate*100:.2f}",
                "unit": "%",
                "sub": f"σ ≥ {ss['shm_an_sigma']:.1f}",
                "signal": rate_signal,
            },
            {
                "label": "Window",
                "value": f"{int(ss['shm_an_window'])}",
                "unit": "samples",
                "sub": "rolling baseline",
            },
            {
                "label": "Worst Excursion",
                "value": f"{worst_dev:+.3f}".rstrip(),
                "unit": unit,
                "sub": _format_ts(df.index[worst_idx]) if worst_idx is not None else "—",
            },
        ],
    )

    # ── Controls + chart ─────────────────────────────────────────────────
    side, main = st.columns([1, 3], gap="medium")
    with side:
        with st.container(key="rgf_panel_an_controls"):
            st.markdown(
                '<div class="rgf-panel-hdr"><span class="rgf-panel-title">'
                'Parameters</span></div>',
                unsafe_allow_html=True,
            )
            new_sensor = st.selectbox(
                "Sensor", cols,
                index=cols.index(ss["shm_an_sensor"]) if ss["shm_an_sensor"] in cols else 0,
                key="shm_an_sensor_sel",
            )
            new_window = st.number_input(
                "Window (samples)", min_value=5, max_value=10_000,
                value=int(ss["shm_an_window"]), step=5,
                key="shm_an_window_inp",
            )
            new_sigma = st.number_input(
                "Sigma threshold", min_value=1.0, max_value=10.0,
                value=float(ss["shm_an_sigma"]), step=0.5, format="%.1f",
                key="shm_an_sigma_inp",
            )
            # Persist controls; rerun if anything changed so the next
            # render re-runs detection with the new params.
            if (new_sensor != ss["shm_an_sensor"]
                    or new_window != ss["shm_an_window"]
                    or new_sigma != ss["shm_an_sigma"]):
                ss["shm_an_sensor"] = new_sensor
                ss["shm_an_window"] = new_window
                ss["shm_an_sigma"] = new_sigma
                st.rerun()
    with main:
        _render_anomaly_chart(df, ss["shm_an_sensor"], flags, s)

    # ── Right-rail flagged-timestamps panel ─────────────────────────────
    if n_anoms:
        section_heading("Flagged samples · first 12", major=False)
        _render_flagged_panel(df, s, flags, ss["shm_an_sensor"])


def _worst_excursion(
    s: pd.Series, flags: pd.Series,
) -> tuple[int | None, float]:
    """Return ``(idx, deviation)`` for the largest |value − mean| anomaly."""
    if not flags.any():
        return None, 0.0
    mu = float(s.mean())
    flagged_vals = s[flags.fillna(False).astype(bool)]
    if flagged_vals.empty:
        return None, 0.0
    devs = (flagged_vals - mu).abs()
    worst_label = devs.idxmax()
    # idxmax returns the index label; map back to integer position
    try:
        worst_pos = s.index.get_loc(worst_label)
    except KeyError:
        return None, 0.0
    if isinstance(worst_pos, slice):
        worst_pos = worst_pos.start
    return int(worst_pos), float(s.iloc[worst_pos] - mu)


def _format_ts(ts) -> str:
    if isinstance(ts, pd.Timestamp):
        return f"{ts:%Y-%m-%d %H:%M}"
    return str(ts)


def _render_anomaly_chart(
    df: pd.DataFrame, col: str,
    flags: pd.Series, s: pd.Series,
) -> None:
    n_anoms = int(flags.sum())

    # Downsample for plotting
    if len(df) > 2000:
        idx = np.linspace(0, len(df) - 1, 2000).astype(int)
    else:
        idx = np.arange(len(df))
    if isinstance(df.index, pd.DatetimeIndex):
        x = (df.index - df.index[0]).total_seconds().to_numpy() / 86400.0
        x_label = f"Days from {df.index[0]:%Y-%m-%d}"
    else:
        x = np.asarray(df.index, dtype=float)
        x_label = "Time"
    x_ds = x[idx]
    y_ds = s.iloc[idx].to_numpy(dtype=float)

    # Anomaly XY pairs from the FULL series (so we don't miss flagged
    # samples that fall between downsample strides).
    anom_xy = [
        (float(x[i]), float(s.iloc[i]))
        for i in np.where(flags.to_numpy())[0]
    ]
    series_list = [
        series(y_ds, color_for_sensor(col, list(df.columns)), col, filled=True),
    ]
    if anom_xy:
        anom_series = series_xy(anom_xy, "#ef4444", "Anomaly", filled=False)
        anom_series["plot"] = "scatter"
        series_list.append(anom_series)

    unit = sensor_unit(col)
    type_lbl = sensor_label(col).split(" (")[0]
    y_label = f"{type_lbl} ({unit})" if unit else type_lbl
    chart_panel(
        f"{col} · {n_anoms} anomalies",
        series_list,
        x_data=x_ds,
        x_label=x_label,
        y_label=y_label,
        height=400,
        actions_html=icon_btn("download", title="Export"),
        key=f"shm_anom_{col}",
    )


def _render_flagged_panel(
    df: pd.DataFrame, s: pd.Series, flags: pd.Series, col: str,
) -> None:
    """Right-rail print_panel listing the first 12 flagged timestamps."""
    flagged_pos = np.where(flags.to_numpy())[0][:12]
    if not len(flagged_pos):
        return
    mu = float(s.mean())
    rows: list[tuple[str, str]] = []
    for i in flagged_pos:
        ts = df.index[i]
        ts_str = _format_ts(ts)
        val = float(s.iloc[i])
        dev = val - mu
        rows.append((ts_str, f"{val:+.4f}  (Δ {dev:+.4f})"))
    print_panel(
        f"Flagged · {col}",
        rows,
        status=f"{int(flags.sum()):,} total",
        hl_label="First flagged",
        hl_value=_format_ts(df.index[flagged_pos[0]]),
    )
