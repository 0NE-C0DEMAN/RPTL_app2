"""Correlation view — pairwise correlation heatmap + rich scatter inspector.

Computes Pearson correlation across every sensor pair, renders the
matrix as a true diverging heatmap (negative red ↔ positive teal,
muted grey at 0, diagonal de-emphasised since r=1 is trivial) with a
colour-scale legend strip, then lets the user pick any pair to see:

* The scatter cloud, time-tinted (early samples lighter, late samples
  darker — exposes when the relationship drifts over the period).
* A least-squares regression line through the cloud.
* Mean reference lines (vertical at <X>, horizontal at <Y>) so the
  four quadrants are obvious.
* r, r², slope, intercept annotated in a stat-mini grid below.
"""
from __future__ import annotations

import html as html_mod

import numpy as np
import streamlit as st

from lib.charts.canvas import chart_panel, icon_btn
from lib.components import (
    empty_state, kpi_strip, page_header, section_heading, stat_mini,
)
from lib.shm import color_for_sensor, get_active_dataset, sensor_unit
from lib.state import get_active_info
from lib.timewindow import apply_time_window, time_window_bar


def render() -> None:
    info = get_active_info()
    if info is None:
        page_header("Correlation", "Pairwise sensor correlation")
        empty_state("database", "No active dataset", "")
        return

    df_full = get_active_dataset()
    if df_full is None or df_full.empty:
        page_header("Correlation", info.source_filename or info.table_name)
        empty_state("alert", "Couldn't load dataset", "")
        return

    page_header(
        "Correlation",
        "Pearson correlation across every sensor pair. "
        "Pick a cell below to inspect the scatter.",
    )

    time_window_bar(df_full)
    df = apply_time_window(df_full)
    if df.empty:
        empty_state("ruler", "No samples in this window",
                    "Try a wider preset to see data again.")
        return

    cols = list(df.columns)
    if len(cols) < 2:
        empty_state("ruler", "Need at least 2 sensors",
                    "Correlation analysis requires multiple columns.")
        return

    # ── Correlation matrix ──────────────────────────────────────────────
    corr = df.corr(numeric_only=True).fillna(0.0)
    cols = list(corr.columns)

    # KPI strip — surface the strongest off-diagonal pairs
    _render_corr_kpi(corr, cols)

    section_heading("Correlation matrix", major=True)
    _render_heatmap(corr, cols)

    # ── Scatter inspector ───────────────────────────────────────────────
    section_heading("Inspect a pair", major=True)
    ss = st.session_state
    ss.setdefault("shm_corr_x", cols[0])
    ss.setdefault("shm_corr_y", cols[1] if len(cols) > 1 else cols[0])

    side, main = st.columns([1, 2.5], gap="medium")
    with side:
        with st.container(key="rgf_panel_corr_pick"):
            st.markdown(
                '<div class="rgf-panel-hdr"><span class="rgf-panel-title">'
                'Pair</span></div>',
                unsafe_allow_html=True,
            )
            ss["shm_corr_x"] = st.selectbox(
                "X axis", cols,
                index=cols.index(ss["shm_corr_x"]) if ss["shm_corr_x"] in cols else 0,
                key="shm_corr_x_sel",
            )
            ss["shm_corr_y"] = st.selectbox(
                "Y axis", cols,
                index=cols.index(ss["shm_corr_y"]) if ss["shm_corr_y"] in cols else 0,
                key="shm_corr_y_sel",
            )

    with main:
        x_col, y_col = ss["shm_corr_x"], ss["shm_corr_y"]
        _render_scatter(df, corr, cols, x_col, y_col)


# ── KPI strip — strongest correlations (off-diagonal, signed) ───────────────
def _render_corr_kpi(corr, cols: list[str]) -> None:
    """4 cells: count of strong pairs, top positive, top negative, average |r|."""
    arr = corr.to_numpy()
    n = len(cols)
    # Off-diagonal upper triangle
    iu = np.triu_indices(n, k=1)
    pairs = arr[iu]
    if not len(pairs):
        return
    abs_pairs = np.abs(pairs)
    avg_abs = float(np.mean(abs_pairs))
    n_strong = int(np.sum(abs_pairs >= 0.7))

    # Best positive + most negative
    pos_mask = pairs > 0
    neg_mask = pairs < 0
    if pos_mask.any():
        pos_idx_local = int(np.argmax(np.where(pos_mask, pairs, -np.inf)))
        i, j = iu[0][pos_idx_local], iu[1][pos_idx_local]
        top_pos = (cols[i], cols[j], float(pairs[pos_idx_local]))
    else:
        top_pos = ("—", "", 0.0)
    if neg_mask.any():
        neg_idx_local = int(np.argmin(np.where(neg_mask, pairs, np.inf)))
        i, j = iu[0][neg_idx_local], iu[1][neg_idx_local]
        top_neg = (cols[i], cols[j], float(pairs[neg_idx_local]))
    else:
        top_neg = ("—", "", 0.0)

    kpi_strip(
        "Pair statistics",
        [
            {
                "label": "Pairs",
                "value": f"{n*(n-1)//2}",
                "unit": "total",
                "sub": f"{n} sensors",
                "lead": True,
            },
            {
                "label": "Strong (|r| ≥ 0.7)",
                "value": str(n_strong),
                "sub": "off-diagonal",
                "signal": "warn" if n_strong else None,
            },
            {
                "label": "Top Positive",
                "value": f"r = {top_pos[2]:+.3f}",
                "sub": f"{top_pos[0]} ↔ {top_pos[1]}".strip(" ↔ "),
                "signal": "pos",
            },
            {
                "label": "Top Negative",
                "value": f"r = {top_neg[2]:+.3f}" if top_neg[2] < 0 else "—",
                "sub": (f"{top_neg[0]} ↔ {top_neg[1]}".strip(" ↔ ")
                        if top_neg[2] < 0 else "no negative pairs"),
                "signal": "neg" if top_neg[2] < 0 else None,
            },
            {
                "label": "Mean |r|",
                "value": f"{avg_abs:.3f}",
                "sub": "avg pair strength",
            },
        ],
    )


# ── Heatmap (HTML + CSS, no canvas) ─────────────────────────────────────────
def _render_heatmap(corr, cols: list[str]) -> None:
    """True diverging heatmap with a colour-scale legend strip on top.

    Diagonal cells (r = 1) are de-emphasised (struck-through font,
    muted bg) so the reader's eye goes to the meaningful off-diagonal
    pairs.
    """
    n = len(cols)
    head_cells = '<th></th>' + "".join(
        f'<th class="rgf-shm-corr-th">{html_mod.escape(c)}</th>' for c in cols
    )
    rows = []
    for r_lbl in cols:
        cells = [f'<th class="rgf-shm-corr-th rgf-shm-corr-th-row">'
                 f'{html_mod.escape(r_lbl)}</th>']
        for c_lbl in cols:
            r = float(corr.loc[r_lbl, c_lbl])
            cells.append(_corr_cell(r, diagonal=(r_lbl == c_lbl)))
        rows.append(f'<tr>{"".join(cells)}</tr>')

    legend_html = _scale_legend_html()
    with st.container(key="rgf_panel_corr_matrix"):
        st.markdown(
            '<div class="rgf-panel-hdr">'
            f'<span class="rgf-panel-title">Pearson r · {n}×{n}</span>'
            f'<div class="rgf-shm-corr-legend">{legend_html}</div>'
            '</div>'
            f'<div class="rgf-shm-corr-wrap"><table class="rgf-shm-corr">'
            f'<thead><tr>{head_cells}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>',
            unsafe_allow_html=True,
        )


# Diverging palette stops — symmetrical around 0 (neutral mid-grey).
# Negative end: warm coral red. Positive end: SHM teal/emerald.
_NEG_RGB = (239, 68, 68)
_POS_RGB = (16, 185, 129)


def _diverging_color(r: float) -> tuple[str, str]:
    """Return (bg, fg) hex/rgba strings for a Pearson r value.

    Alpha scales with |r|^0.85 so weak correlations fade to near-neutral
    while strong ones saturate to the family colour. Foreground flips
    to white when the cell is dark enough to need it.
    """
    a = min(1.0, abs(r)) ** 0.85
    if r >= 0:
        rgb = _POS_RGB
    else:
        rgb = _NEG_RGB
    bg = f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{0.78 * a:.3f})"
    fg = "#ffffff" if a >= 0.55 else "var(--text)"
    return bg, fg


def _corr_cell(r: float, *, diagonal: bool = False) -> str:
    """Coloured table cell — diverging palette, diagonal de-emphasised."""
    if not np.isfinite(r):
        return '<td class="rgf-shm-corr-cell rgf-shm-corr-cell-na">—</td>'
    if diagonal:
        return (
            '<td class="rgf-shm-corr-cell rgf-shm-corr-cell-diag" '
            f'title="self-correlation">{r:+.2f}</td>'
        )
    bg, fg = _diverging_color(r)
    return (
        f'<td class="rgf-shm-corr-cell" '
        f'style="background:{bg}; color:{fg};">'
        f'{r:+.2f}</td>'
    )


def _scale_legend_html() -> str:
    """Compact horizontal colour-scale strip — −1 ▮▯▮ +1."""
    stops = []
    for r in np.linspace(-1.0, 1.0, 21):
        bg, _ = _diverging_color(float(r))
        stops.append(f'<span class="rgf-shm-corr-stop" style="background:{bg}"></span>')
    return (
        '<span class="rgf-shm-corr-legend-end">−1.0</span>'
        f'<span class="rgf-shm-corr-bar">{"".join(stops)}</span>'
        '<span class="rgf-shm-corr-legend-end">+1.0</span>'
    )


# ── Scatter inspector ───────────────────────────────────────────────────────
def _render_scatter(df, corr, cols: list[str], x_col: str, y_col: str) -> None:
    sub = df[[x_col, y_col]].dropna()
    if sub.empty:
        empty_state(
            "ruler", "No overlapping samples",
            f"{x_col} and {y_col} have no rows where both are non-NaN.",
        )
        return

    n_total = len(sub)
    # Down-sample for plotting (preserves order so time-tinting still works).
    if n_total > 5_000:
        idx = np.linspace(0, n_total - 1, 5_000).astype(int)
        sub = sub.iloc[idx]

    x = sub[x_col].to_numpy(dtype=float)
    y = sub[y_col].to_numpy(dtype=float)

    # Linear fit: y = slope * x + intercept, plus r and r²
    slope, intercept = np.polyfit(x, y, 1)
    r_val = float(corr.loc[y_col, x_col])
    r_sq = r_val ** 2
    x_mean = float(np.mean(x))
    y_mean = float(np.mean(y))

    base_color = color_for_sensor(y_col, cols)

    # ── Build series list ───────────────────────────────────────────────
    # 1) Time-binned scatter — split the cloud into 4 quartiles by sample
    #    order so each quartile gets its own legend chip + alpha. Engineers
    #    can see whether the relationship drifted over the period.
    quart_palette = _time_palette(base_color, n=4)
    quart_labels = ["Q1 · earliest", "Q2", "Q3", "Q4 · latest"]
    n = len(x)
    series_list: list[dict] = []
    for q in range(4):
        lo = (q * n) // 4
        hi = ((q + 1) * n) // 4
        if hi <= lo:
            continue
        xs_q = [[float(x[i]), float(y[i])] for i in range(lo, hi)]
        series_list.append({
            "_y_raw": None, "data": None,
            "color": quart_palette[q],
            "label": quart_labels[q],
            "dashed": False, "filled": False, "plot": "scatter",
            "axis": "left",
            "xy": xs_q,
        })

    # 2) Regression line — extend across the full x-range
    xr = np.array([float(np.min(x)), float(np.max(x))])
    yr = slope * xr + intercept
    series_list.append({
        "_y_raw": None, "data": None,
        "color": "#ffffff",
        "label": f"fit · y = {slope:+.4f} x + {intercept:+.4f}",
        "dashed": False, "filled": False, "plot": "line",
        "axis": "left",
        "xy": [[float(xr[0]), float(yr[0])], [float(xr[1]), float(yr[1])]],
    })

    # 3) Mean reference lines — horizontal & vertical at the means.
    #    Drawn as XY pairs with a light grey colour and dashed style.
    y_min, y_max = float(np.min(y)), float(np.max(y))
    x_min, x_max = float(np.min(x)), float(np.max(x))
    series_list.append({
        "_y_raw": None, "data": None,
        "color": "#64748b",
        "label": f"mean {x_col} = {x_mean:.3f}",
        "dashed": True, "filled": False, "plot": "line",
        "axis": "left",
        "xy": [[x_mean, y_min], [x_mean, y_max]],
    })
    series_list.append({
        "_y_raw": None, "data": None,
        "color": "#64748b",
        "label": f"mean {y_col} = {y_mean:.3f}",
        "dashed": True, "filled": False, "plot": "line",
        "axis": "left",
        "xy": [[x_min, y_mean], [x_max, y_mean]],
    })

    x_unit = sensor_unit(x_col)
    y_unit = sensor_unit(y_col)
    x_axis_lbl = f"{x_col} ({x_unit})" if x_unit else x_col
    y_axis_lbl = f"{y_col} ({y_unit})" if y_unit else y_col

    chart_panel(
        f"{y_col} vs {x_col}",
        series_list,
        x_data=[],
        x_label=x_axis_lbl, y_label=y_axis_lbl,
        height=380,
        actions_html=icon_btn("download", title="Export"),
        key=f"shm_corr_scatter_{x_col}_{y_col}",
    )

    # ── Stat-mini grid: r · r² · slope · intercept · n ──────────────────
    chips = "".join([
        stat_mini("Pearson r", f"{r_val:+.4f}"),
        stat_mini("r²",        f"{r_sq:.4f}"),
        stat_mini("Slope",     f"{slope:+.4f}",
                  f"{y_unit}/{x_unit}" if (y_unit and x_unit) else ""),
        stat_mini("Intercept", f"{intercept:+.4f}", y_unit),
        stat_mini("Mean X",    f"{x_mean:.3f}", x_unit),
        stat_mini("Mean Y",    f"{y_mean:.3f}", y_unit),
        stat_mini("n",         f"{n_total:,}"),
    ])
    st.markdown(
        f'<div class="rgf-stat-mini-grid">{chips}</div>',
        unsafe_allow_html=True,
    )


# ── Time-tint palette helper ────────────────────────────────────────────────
def _time_palette(base_hex: str, n: int = 4) -> list[str]:
    """Build N shades of ``base_hex`` from very light to fully saturated.

    Engineers reading a scatter want to see whether the relationship
    has drifted over the recording period — colouring the cloud by
    time-quartile makes that visible without forcing a separate plot.
    """
    h = base_hex.lstrip("#")
    r0 = int(h[0:2], 16)
    g0 = int(h[2:4], 16)
    b0 = int(h[4:6], 16)
    out = []
    for q in range(n):
        # alpha ramps 0.32 → 0.95 across quartiles
        a = 0.32 + (q / max(1, n - 1)) * (0.95 - 0.32)
        out.append(f"rgba({r0},{g0},{b0},{a:.3f})")
    return out
