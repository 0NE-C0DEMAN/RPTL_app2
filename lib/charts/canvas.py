"""
lib/charts/canvas.py — Shared Canvas chart panel (ported from the design's
``components/charts.jsx`` + ``ui.jsx::ChartPanel``).

Every view that wants a chart calls ``chart_panel(...)`` and gets:

* A self-contained ChartPanel card (surface bg, 10px radius, 1px border).
* Design-spec grid (8 horizontal / 10 vertical lines, slate 0.1 alpha).
* JetBrains Mono Y/X ticks, DM Sans axis labels.
* Hover crosshair with a dark-navy tooltip (colour dot + label + mono value).
* Zoom/pan toolbar: `<` pan-left, `+` zoom-in, `%` label, `−` zoom-out,
  `>` pan-right, Reset, Fullscreen.
* Mousewheel zoom toward the cursor.
* Click-drag box-zoom on the canvas + double-click reset.
* `download` icon button → exports the current canvas as a PNG.
* Toggle groups for SmallBtns in the header:
    - ``group="unit"`` + ``data={"factor": "<float>"}`` — multiplies the
      y values by the factor (mm ↔ µm, etc.) and updates the y-axis label.
    - ``group="trace"`` + ``data={"label": "<series label>"}`` — show only
      the trace with the matching ``label``.

The entire panel renders inside a single ``st.components.v1.html`` iframe
so Streamlit's markdown sanitiser can't flatten the flex layout or strip
``<canvas>`` / nested ``<div>`` wrappers. All colours come through as
concrete hex values interpolated from ``lib.tokens`` so the iframe
doesn't need to reach into the host stylesheet.

Public:
    chart_panel(title, series, x_data, *, height, x_label, y_label,
                actions_html, key)   — render one ChartPanel
    series(data, color, label, *, dashed, filled, downsample_n) — series dict
    small_btn(label, *, active, group, data)                    — SmallBtn HTML
    icon_btn(icon_name, *, title)                               — IconBtn HTML
"""
from __future__ import annotations

import html as html_mod
import json
from typing import Iterable

import numpy as np
import streamlit as st

from lib.icons import svg
# Token imports moved to lib/charts/_canvas_template.py along with the
# iframe HTML/JS that consumes them.


# ── Public helpers (Python side) ─────────────────────────────────────────────
def series_xy(
    xy_points: Iterable,
    color: str,
    label: str,
    *,
    dashed: bool = False,
    filled: bool = False,
) -> dict:
    """Package one cross-plot series (each point carries its own x, y).

    Required when the x-axis is a data dimension that isn't monotonic —
    hysteresis loops (Load vs Displacement), phase space (vel vs disp),
    etc. Each element of ``xy_points`` is a ``(x, y)`` pair; ``None`` /
    ``NaN`` in either slot acts as a pen-up gap (useful when a single
    series needs to draw discontinuous segments, e.g. box-plot polygon
    followed by whiskers).
    """
    def _cell(val):
        if val is None:
            return None
        f = float(val)
        return None if np.isnan(f) else f

    pts: list[list[float | None]] = []
    for p in xy_points:
        pts.append([_cell(p[0]), _cell(p[1])])
    return {
        "xy": pts,
        "color": color, "label": label,
        "dashed": dashed, "filled": filled,
    }


def series(
    data: Iterable[float],
    color: str,
    label: str,
    *,
    dashed: bool = False,
    filled: bool = True,
    downsample_n: int | None = 1500,
    plot: str = "line",
    axis: str = "left",
) -> dict:
    """Package one series for ``chart_panel``.

    ``plot`` selects the draw mode:
      - ``line``    (default) — stroked polyline; ``filled=True`` adds
                     a gradient area under it.
      - ``area``    alias for ``line`` + ``filled=True``.
      - ``scatter`` dots only, no connecting line.
      - ``bar``     vertical bars from y=0 to each value.

    ``axis`` chooses which y-scale the series binds to:
      - ``left``  (default) — primary y-axis (single-axis charts use this)
      - ``right`` — secondary y-axis. When at least one series declares
        ``axis="right"``, the chart draws two y-scales side-by-side and
        each series renders against its own. Use for combos where the
        magnitudes differ by orders of magnitude (Load kN vs Velocity
        mm/s, Load kN vs Accel m/s², etc.).

    Downsampling is deferred to ``chart_panel`` so x + every y series
    get reduced at the **same indices** — and using LTTB (Largest
    Triangle Three Buckets), which preserves peaks / valleys in RPLT-
    style impulsive signals. Uniform stride-based downsampling used to
    silently drop the impact peak whenever it landed between strides.

    ``downsample_n`` is still honoured as an UPPER BOUND on the per-series
    budget — chart_panel will never emit more than this many points for
    a series — but the actual index picking happens in chart_panel.

    ``None`` / ``NaN`` values in the data become ``null`` in the payload;
    the canvas treats them as pen-up gaps so you can draw split or
    discontinuous lines without forcing per-series x-arrays.
    """
    arr = np.asarray(data, dtype=float)
    # "area" is a convenience alias for a filled line.
    if plot == "area":
        plot, filled = "line", True
    # NOTE: we keep the full-resolution array here and let chart_panel
    # subsample jointly with x. Previously this did uniform-stride
    # downsample which dropped peaks for impulsive signals.
    return {
        "_y_raw": arr,  # full-res, consumed by chart_panel + dropped
        "data": None,   # filled in by chart_panel after joint sampling
        "color": color, "label": label,
        "dashed": dashed, "filled": filled,
        "plot": plot,
        "axis": "right" if axis == "right" else "left",
        "_budget": downsample_n,
    }


def small_btn(
    label: str,
    *,
    active: bool = False,
    group: str = "",
    data: dict[str, str] | None = None,
) -> str:
    """SmallBtn HTML (matches ``ui.jsx::SmallBtn``)."""
    cls = "small-btn" + (" active" if active else "")
    attrs = [f'class="{cls}"', 'type="button"']
    if group:
        attrs.append(f'data-group="{group}"')
    for k, v in (data or {}).items():
        attrs.append(f'data-{k}="{html_mod.escape(v)}"')
    return f'<button {" ".join(attrs)}>{html_mod.escape(label)}</button>'


def icon_btn(icon_name: str, *, title: str = "") -> str:
    """IconBtn HTML (28×28 square, 14px SVG). Matches ``ui.jsx::IconBtn``."""
    return (
        f'<button type="button" class="icon-btn" title="{html_mod.escape(title)}">'
        f'{svg(icon_name, size=14)}'
        f'</button>'
    )


def chart_panel(
    title: str,
    series_list: list[dict],
    x_data,
    *,
    height: int = 240,
    x_label: str = "Time (s)",
    y_label: str = "",
    y_label_right: str = "",
    actions_html: str = "",
    key: str = "",
    annotations: list[dict] | None = None,
) -> None:
    """Render one ChartPanel with a Canvas-based chart body + toolbar.

    ``annotations`` is an optional list of marker / line specs drawn on
    top of the series. Each dict looks like one of:

        {"type": "point",  "x": <val>, "y": <val>,
         "label": "Peak", "color": "#10b981", "shape": "circle|diamond",
         "label_offset": "top|right|bottom|left"}

        {"type": "vline",  "x": <val>,
         "label": "v=0", "color": "#ef4444"}

    Values are in data units (same scale as ``x_data`` / series) — the
    canvas converts to pixels via its internal ``toX`` / ``toY``.
    """
    key = key or title.replace(" ", "_").lower()
    # Empty x_data is legal when every series is XY-pair mode.
    x_arr = np.asarray(x_data, dtype=float) if x_data is not None and len(x_data) else np.array([])

    # ── Joint peak-preserving downsample ───────────────────────────────
    # Pick a single index set using LTTB against the composite envelope
    # of every series (max-abs across series at each sample), then apply
    # those indices to x AND every series. Compared with uniform-stride
    # decimation this keeps the impact peak visible for 166K-sample
    # acquisition dumps where the peak would otherwise fall between
    # strides. See ``_joint_downsample_indices`` for the policy.
    if len(x_arr):
        budget = min(
            (s.get("_budget") or 1500)
            for s in series_list if "_y_raw" in s
        ) if any("_y_raw" in s for s in series_list) else 1500
        idx = _joint_downsample_indices(x_arr, series_list, n=budget)
        x_arr_ds = x_arr[idx] if idx is not None else x_arr
    else:
        idx = None
        x_arr_ds = x_arr

    # Materialise each series' data array at the chosen indices. XY-
    # pair series are passed through unchanged (their own x-values
    # aren't derived from the shared x-axis).
    clean_series: list[dict] = []
    for s in series_list:
        s_out = {k: v for k, v in s.items() if not k.startswith("_")}
        if "xy" in s:
            clean_series.append(s_out)
            continue
        raw_y = s.get("_y_raw")
        if raw_y is None:
            # Already materialised (tests / external callers). Leave alone.
            clean_series.append(s_out)
            continue
        y = raw_y
        if idx is not None:
            y = y[idx]
        s_out["data"] = [None if np.isnan(v) else float(v) for v in y.tolist()]
        clean_series.append(s_out)

    x_vals = x_arr_ds.tolist() if len(x_arr_ds) else []

    # Sanitise the key so it's safe as a Streamlit widget key (and as a
    # CSS class prefix the JS bridge can target for Download/Print).
    safe_key = _sanitise_key(key)
    payload = json.dumps({
        "series": clean_series,
        "x": x_vals,
        "xLabel": x_label,
        "yLabel": y_label,
        "yLabelRight": y_label_right,
        "annotations": annotations or [],
    })

    # Header (46) + toolbar row (38) + legend strip (28) + canvas (height) + padding (20).
    # Legend strip reserves a single row for sensor colour chips; charts
    # with many series wrap into a second row inside the iframe (the
    # outer container can scroll/clip if needed — the chips re-flow).
    total_height = 46 + 38 + 28 + height + 20

    doc = _iframe_doc(
        title=html_mod.escape(title),
        actions_html=actions_html,
        payload=payload,
        height=height,
        key=html_mod.escape(key),
    )
    # Wrap the iframe in a keyed st.container so the DOM has a findable
    # class (st-key-rgf_chart_panel_<key>) for the JS bridge to target —
    # needed for the Chart Builder's Download button and any future
    # "which iframe was clicked" coordination.
    with st.container(key=f"rgf_chart_panel_{safe_key}"):
        st.components.v1.html(doc, height=total_height, scrolling=False)


# ── Public helpers (internal) ────────────────────────────────────────────────
def _sanitise_key(key: str) -> str:
    """Strip characters that would break an st.container key (must be a
    valid Python identifier-ish) and CSS class (no spaces / specials)."""
    import re
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", key)
    return cleaned or "panel"


# ── Internal: downsample helper ──────────────────────────────────────────────
def _downsample(arr: np.ndarray, n: int, *, keep_nans: bool = False) -> np.ndarray:
    """Uniform-stride downsample to at most ``n`` points.

    Kept for back-compat with any callers that don't have an x-axis
    context. Prefer ``_joint_downsample_indices`` where possible — it's
    peak-preserving (LTTB), which matters enormously for RPLT impact
    signals that sit as a narrow spike in a 166k-sample acquisition.
    """
    arr = np.asarray(arr, dtype=float)
    if not keep_nans:
        arr = arr[~np.isnan(arr)]
    if len(arr) <= n:
        return arr
    idx = np.linspace(0, len(arr) - 1, n).astype(int)
    return arr[idx]


def _joint_downsample_indices(
    x: np.ndarray,
    series_list: list[dict],
    *,
    n: int,
) -> np.ndarray | None:
    """Pick ``n`` indices that jointly preserve the shape of every series.

    Strategy:
      * If total samples ≤ n, return ``None`` (no downsample).
      * Build a composite envelope ``y_env = max_i |y_i|`` — the biggest
        magnitude across all series at each sample. This way LTTB keeps
        points where ANY series spikes (peak load, peak accel, etc.).
      * Run LTTB against ``(x, y_env)`` to pick ``n`` indices. LTTB picks
        the point in each bucket that maximises the triangle area with
        the previous kept point + next bucket mean — provably preserves
        visual extrema.
      * Fall back to uniform stride if LTTB fails (e.g. lib missing or
        NaN-heavy input).

    Returns ``np.ndarray[int]`` of picked indices, or ``None`` to mean
    "use everything".
    """
    N = len(x)
    if N <= n:
        return None

    # Build composite envelope from all y-series (ignore XY-pair series
    # — they don't share the x-axis). Fill NaN with 0 so they don't
    # dominate the max; the NaN-as-gap semantics are preserved later
    # when each series is materialised.
    envelopes: list[np.ndarray] = []
    for s in series_list:
        if "_y_raw" not in s:
            continue
        y = np.asarray(s["_y_raw"], dtype=float)
        if len(y) != N:
            # Mismatched series — ignore it in the envelope. It'll still
            # render, just won't influence index picking.
            continue
        y_safe = np.nan_to_num(y, nan=0.0)
        envelopes.append(np.abs(y_safe))
    if not envelopes:
        # No y-series to guide LTTB — fall back to uniform stride.
        return np.linspace(0, N - 1, n).astype(int)

    y_env = np.max(np.stack(envelopes), axis=0)

    # LTTB. Uses `lttb` package if available; otherwise uniform stride.
    try:
        import lttb
        # lttb expects a 2-column array of (x, y). Use index as x since
        # our x can be non-uniform or unsorted (defensive). Picking
        # indices is what we want anyway — we return the index positions.
        pairs = np.column_stack([np.arange(N, dtype=float), y_env])
        out = lttb.downsample(pairs, n_out=n)
        # out is (n, 2); column 0 holds the original index position.
        return out[:, 0].astype(int)
    except Exception:
        return np.linspace(0, N - 1, n).astype(int)


# Iframe HTML/JS template lives in a sibling module to keep this file
# at a readable size — chart_panel imports it via a relative import.
from lib.charts._canvas_template import _iframe_doc as _iframe_doc  # noqa: F401,E402
