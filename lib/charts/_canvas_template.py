"""lib/charts/_canvas_template.py — the inline JS+HTML iframe template
for ``chart_panel``.

Internal helper. The Python f-string carries CSS / JS that draws the
canvas chart, with ``{TEXT_3}`` / ``{ACCENT}`` / etc. interpolated from
``lib.tokens`` so the iframe doesn't need to reach into the host
stylesheet. Kept in its own module so the public Python surface in
``canvas.py`` stays readable (~360 lines instead of 1,400).

Imports + the function itself were lifted verbatim from the bottom of
``canvas.py``; no behaviour change. ``canvas.py`` re-exports
``_iframe_doc`` so any external callers (none currently, but defensive)
keep working.
"""
from __future__ import annotations

from lib.tokens import (
    ACCENT, ACCENT_BORDER, ACCENT_DEEP, ACCENT_TINT,
    BG_SOFT, BORDER, NAVY, NAVY_LIGHT, SURFACE,
    TEXT, TEXT_2, TEXT_3,
)


# ── Internal: iframe document template ───────────────────────────────────────
def _iframe_doc(
    *, title: str, actions_html: str, payload: str, height: int, key: str,
) -> str:
    """Return the full self-contained HTML document for one ChartPanel."""
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    font-family: 'DM Sans', system-ui, sans-serif;
    background: transparent; color: {TEXT};
    -webkit-font-smoothing: antialiased; overflow: hidden;
  }}
  .panel {{
    background: {SURFACE}; border: 1px solid {BORDER};
    border-radius: 10px; overflow: hidden;
    display: flex; flex-direction: column;
  }}
  .hdr {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 14px 18px 0; gap: 8px;
  }}
  .title {{ font-size: 13px; font-weight: 600; color: {TEXT}; }}
  .actions {{ display: flex; gap: 4px; align-items: center; }}
  .small-btn {{
    padding: 4px 10px; font-size: 11px; font-weight: 400;
    background: transparent; color: {TEXT_3};
    border: 1px solid {BORDER}; border-radius: 6px;
    cursor: pointer; font-family: inherit;
    line-height: 1.4; transition: all 0.12s;
  }}
  .small-btn:hover {{ color: {TEXT}; }}
  .small-btn.active {{
    /* Active SmallBtn — accent-tinted bg + accent text. Light theme:
       the dark NAVY_LIGHT/white-text combo from the dark theme would
       look out of place, so we use the accent-tint pill convention
       instead (matches the legend chips + KPI accent cells). */
    background: {ACCENT_TINT}; color: {ACCENT_DEEP};
    border: 1px solid {ACCENT_BORDER};
    padding: 4px 11px; font-weight: 600;
  }}
  .icon-btn {{
    width: 28px; height: 28px; padding: 0;
    display: inline-flex; align-items: center; justify-content: center;
    background: none; border: 1px solid {BORDER};
    border-radius: 6px; cursor: pointer; color: {TEXT_3};
    transition: all 0.12s;
  }}
  .icon-btn:hover {{ color: {TEXT}; border-color: {TEXT_3}; }}
  .icon-btn svg {{ width: 14px; height: 14px; }}

  .tb-row {{
    display: flex; justify-content: flex-end; gap: 6px;
    padding: 8px 12px 6px;
  }}
  /* ── Legend strip — colour swatch + label per series ───────────────────
     Sits between the toolbar and the canvas. Click a chip to hide/show
     that series — the colour-coded chips are the only way users can
     differentiate five LVDTs (each rendered in a different shade of blue)
     once they're stacked on the same overlay.                          */
  .legend {{
    display: flex; flex-wrap: wrap; gap: 6px 14px;
    padding: 0 14px 6px; align-items: center;
    font-size: 11px; color: {TEXT_3};
  }}
  .legend .lg-chip {{
    display: inline-flex; align-items: center; gap: 6px;
    padding: 2px 8px 2px 4px; border-radius: 999px;
    background: transparent; border: 1px solid transparent;
    cursor: pointer; transition: background 0.12s, border-color 0.12s, opacity 0.12s;
    user-select: none;
  }}
  .legend .lg-chip:hover {{ background: {BG_SOFT}; border-color: {BORDER}; }}
  .legend .lg-chip.lg-off {{ opacity: 0.36; text-decoration: line-through; }}
  .legend .lg-dot {{
    width: 10px; height: 10px; border-radius: 50%;
    flex-shrink: 0; box-shadow: 0 0 0 1px rgba(0,0,0,0.25) inset;
  }}
  .legend .lg-dash {{
    width: 14px; height: 0; border-top: 2px dashed currentColor;
  }}
  .legend .lg-axis {{
    font-size: 9px; opacity: 0.7; padding-left: 2px;
    font-family: 'JetBrains Mono', monospace;
  }}
  .toolbar {{
    display: inline-flex; border-radius: 7px; overflow: hidden;
    border: 1px solid {BORDER}; background: {BG_SOFT};
  }}
  .toolbar button {{
    width: 30px; height: 26px;
    display: inline-flex; align-items: center; justify-content: center;
    background: transparent; border: none; cursor: pointer;
    color: {TEXT_3}; transition: all 0.12s; font-size: 13px; padding: 0;
  }}
  .toolbar button:hover {{ color: {TEXT}; background: {BG_SOFT}; }}
  .toolbar button svg {{ width: 12px; height: 12px; }}
  .toolbar .zlabel {{
    /* charts.jsx ChartToolbar zoom label: subtle tinted bg that reads as
       a non-button slot between the zoom buttons. Design light-theme:
       #f8f9fb. Dark equivalent: BG_SOFT (slightly raised vs SURFACE). */
    padding: 0 8px; font-size: 10px;
    font-family: 'JetBrains Mono', monospace; color: {TEXT_3};
    display: inline-flex; align-items: center;
    background: {BG_SOFT};
    border-left: 1px solid {BORDER}; border-right: 1px solid {BORDER};
    min-width: 42px; justify-content: center;
  }}
  .toolbar .divider {{ width: 1px; background: {BORDER}; }}
  .toolbar .reset-btn {{
    padding: 0 10px; width: auto; font-size: 10px;
    font-family: inherit; font-weight: 500;
  }}

  .body {{ position: relative; padding: 0 12px 12px; }}
  canvas {{
    width: 100%; height: {height}px; display: block;
    cursor: crosshair; user-select: none;
  }}

  /* ── Fullscreen — fill the viewport, stretch the canvas vertically ─── */
  :fullscreen .panel,
  :-webkit-full-screen .panel {{
    width: 100vw; height: 100vh; border-radius: 0; border: none;
  }}
  :fullscreen .body,
  :-webkit-full-screen .body {{
    flex: 1; padding: 0 16px 16px;
  }}
  :fullscreen canvas,
  :-webkit-full-screen canvas {{
    height: calc(100vh - 46px - 38px - 16px) !important;
  }}
  .tt {{
    /* Hover tooltip — opaque card on a soft drop shadow. Was navy
       in the dark theme; now a high-contrast white card with deep-
       navy text + an accent-tinted left rail for visual anchoring. */
    position: absolute; background: {SURFACE};
    border: 1px solid {BORDER}; border-left: 3px solid {ACCENT};
    border-radius: 8px;
    padding: 10px 14px 10px 12px; pointer-events: none; z-index: 10;
    box-shadow: 0 6px 20px rgba(15, 23, 51, 0.16),
                0 1px 3px rgba(15, 23, 51, 0.08);
    min-width: 140px; display: none;
  }}
  .tt-hdr {{
    font-size: 10px; color: {TEXT_3};
    font-family: 'JetBrains Mono', monospace; margin-bottom: 5px;
    letter-spacing: 0.04em;
  }}
  .tt-row {{ display: flex; align-items: center; gap: 8px; margin-top: 3px; }}
  .tt-dot {{ width: 8px; height: 8px; border-radius: 4px; flex-shrink: 0; }}
  .tt-lbl {{ font-size: 11px; color: {TEXT_2}; flex: 1; }}
  .tt-val {{
    font-size: 12px; color: {TEXT};
    font-family: 'JetBrains Mono', monospace; font-weight: 600;
    font-variant-numeric: tabular-nums;
  }}
</style></head>
<body>
<div class="panel">
  <div class="hdr">
    <span class="title">{title}</span>
    <div class="actions">{actions_html}</div>
  </div>
  <div class="tb-row">
    <div class="toolbar">
      <button data-action="pan-left" title="Pan left"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg></button>
      <button data-action="zoom-in" title="Zoom in"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg></button>
      <span class="zlabel" id="zlabel">100%</span>
      <button data-action="zoom-out" title="Zoom out"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14"/></svg></button>
      <button data-action="pan-right" title="Pan right"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg></button>
      <div class="divider"></div>
      <button data-action="reset" class="reset-btn" title="Reset zoom">Reset</button>
      <div class="divider"></div>
      <button data-action="fullscreen" title="Fullscreen"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3"/></svg></button>
    </div>
  </div>
  <div class="legend" id="legend"></div>
  <div class="body">
    <canvas id="c"></canvas>
    <div class="tt" id="tt"></div>
  </div>
</div>
<script>
(function() {{
  const DATA = {payload};
  // Clone series for the in-iframe working copy. Either `data` (shared-x
  // time-series) or `xy` (cross-plot pairs) will be present — copy
  // whichever is defined. Copying `undefined.slice()` would crash and
  // blank the whole panel.
  const SERIES0 = DATA.series.map(s => ({{
    ...s,
    data: Array.isArray(s.data) ? s.data.slice() : undefined,
    xy: Array.isArray(s.xy) ? s.xy.map(p => p.slice()) : undefined,
    visible: true,
  }}));
  let unitFactor = 1;
  // View mode — set by data-group="mode" SmallBtns:
  //   "overlay" (default) — all series share one y-axis
  //   "stacked"           — every series draws as a filled area from y=0
  //                         (good for showing contribution banding)
  //   "split"             — each shared-x series gets its own horizontal
  //                         band with an independent y-scale — useful when
  //                         traces differ in magnitude (Raw vs Smoothed
  //                         acceleration where smoothing collapses the
  //                         range 3x)
  let viewMode = 'overlay';

  const canvas = document.getElementById('c');
  const tt = document.getElementById('tt');
  const legendEl = document.getElementById('legend');
  const ctx = canvas.getContext('2d');
  const PAD = {{ l: 56, r: 16, t: 12, b: 44 }};

  // ── Legend strip ────────────────────────────────────────────────────────
  // Build chips for every series — colour swatch + label + (axis tag if
  // the chart is dual-axis). Click a chip to toggle the series in/out of
  // the chart. Hidden internal-helper labels (prefix "_") are skipped so
  // mean/min/max overlays from views/trend.py don't clutter the strip.
  function buildLegend() {{
    if (!legendEl) return;
    const hasRight = SERIES0.some(s => s.axis === 'right');
    legendEl.innerHTML = '';
    SERIES0.forEach((s, i) => {{
      const lbl = (s.label || '').trim();
      if (!lbl || lbl.startsWith('_')) return;
      const chip = document.createElement('span');
      chip.className = 'lg-chip' + (s.visible ? '' : ' lg-off');
      chip.dataset.idx = String(i);
      const dot = document.createElement('span');
      if (s.dashed) {{
        dot.className = 'lg-dash';
        dot.style.color = s.color;
      }} else {{
        dot.className = 'lg-dot';
        dot.style.background = s.color;
      }}
      const text = document.createElement('span');
      text.textContent = lbl;
      chip.appendChild(dot);
      chip.appendChild(text);
      if (hasRight) {{
        const ax = document.createElement('span');
        ax.className = 'lg-axis';
        ax.textContent = s.axis === 'right' ? '↦R' : '↤L';
        chip.appendChild(ax);
      }}
      chip.addEventListener('click', () => {{
        s.visible = !s.visible;
        chip.classList.toggle('lg-off', !s.visible);
        try {{ draw(); }} catch (e) {{}}
      }});
      legendEl.appendChild(chip);
    }});
  }}
  buildLegend();

  // PAD.b reserves room at the bottom for X ticks (y = ch+8) AND the
  // X-axis label (y = h-6, textBaseline='bottom'). 40px keeps them from
  // crowding and stops the label clipping off the canvas edge.
  let zoom = 1, panOffset = 0;
  let hover = null;     // integer index for shared-x panels
  let hoverXY = null;   // {{series, idx, x, y, px, py}} for XY cross-plots
  let isDragging = false, dragStart = null, selectionBox = null;

  const hexA = (hex, a) => {{
    const h = hex.replace('#','');
    return `rgba(${{parseInt(h.substring(0,2),16)}},${{parseInt(h.substring(2,4),16)}},${{parseInt(h.substring(4,6),16)}},${{a}})`;
  }};
  const fmtY = v => {{
    const a = Math.abs(v);
    if (a === 0) return '0';
    if (a >= 10000) return (v/1000).toFixed(1) + 'k';
    if (a >= 100) return v.toFixed(0);
    if (a >= 1) return v.toFixed(1);
    return v.toFixed(3);
  }};
  const fmtX = (v, range) => {{
    const a = Math.abs(v);
    // Engineering suffixes so huge ranges (e.g., microsecond counters
    // hitting 10M) read as "9.8M" instead of "9,830,491".
    if (a >= 1e9)   return (v / 1e9).toFixed(a >= 1e10 ? 0 : 1) + 'G';
    if (a >= 1e6)   return (v / 1e6).toFixed(a >= 1e7 ? 0 : 1) + 'M';
    if (a >= 10000) return (v / 1000).toFixed(a >= 1e5 ? 0 : 1) + 'k';
    const p = range < 0.01 ? 5 : range < 1 ? 4 : range < 10 ? 3 : 1;
    return v.toFixed(p);
  }};
  const getActive = () => SERIES0.filter(s => s.visible).map(s => ({{
    ...s,
    // Shared-x series: scale y by unitFactor (for mm/µm toggle), keeping
    // null gap markers as null (null * anything != null).
    data: Array.isArray(s.data)
      ? s.data.map(v => (v === null || v === undefined ? null : v * unitFactor))
      : undefined,
    // XY series: unitFactor not applied (cross-plots pass raw units).
    xy: Array.isArray(s.xy) ? s.xy : undefined,
  }}));
  const visibleRange = () => {{
    const win = 1 / zoom;
    const start = Math.max(0, Math.min(panOffset, 1 - win));
    return {{ start, end: start + win }};
  }};

  // Find the XY-series point nearest to a pixel position. Recomputes the
  // bounds + toX/toY locally so mousemove doesn't have to race with the
  // last-draw state. Returns {{series, idx, x, y}} or null if the cursor
  // is further than the hit radius from every point.
  const _HIT_RADIUS_SQ = 30 * 30;
  const _findNearestXY = (mx, my) => {{
    let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
    const active = getActive();
    for (const s of active) {{
      if (!Array.isArray(s.xy)) continue;
      for (const p of s.xy) {{
        const xv = p[0], yv = p[1];
        if (xv !== null && xv !== undefined && !Number.isNaN(xv)) {{
          if (xv < xMin) xMin = xv; if (xv > xMax) xMax = xv;
        }}
        if (yv !== null && yv !== undefined && !Number.isNaN(yv)) {{
          if (yv < yMin) yMin = yv; if (yv > yMax) yMax = yv;
        }}
      }}
    }}
    if (xMin === Infinity) return null;
    const yR = (yMax - yMin) || 1; yMin -= yR * 0.08; yMax += yR * 0.08;
    const xR = (xMax - xMin) || 1; xMin -= xR * 0.04; xMax += xR * 0.04;
    const rect = canvas.getBoundingClientRect();
    const w = rect.width, h = rect.height;
    const cw = w - PAD.l - PAD.r, ch = h - PAD.t - PAD.b;
    const _toX = v => PAD.l + ((v - xMin) / (xMax - xMin)) * cw;
    const _toY = v => PAD.t + ch - ((v - yMin) / (yMax - yMin)) * ch;
    let best = null, bestDist = _HIT_RADIUS_SQ;
    for (const s of active) {{
      if (!Array.isArray(s.xy)) continue;
      for (let i = 0; i < s.xy.length; i++) {{
        const p = s.xy[i];
        if (p[0] === null || p[1] === null ||
            Number.isNaN(p[0]) || Number.isNaN(p[1])) continue;
        const dx = _toX(p[0]) - mx;
        const dy = _toY(p[1]) - my;
        const d = dx * dx + dy * dy;
        if (d < bestDist) {{
          bestDist = d;
          best = {{ series: s, idx: i, x: p[0], y: p[1] }};
        }}
      }}
    }}
    return best;
  }};
  const updZoomLabel = () => {{ document.getElementById('zlabel').textContent = Math.round(zoom * 100) + '%'; }};

  function resize() {{
    const bodyRect = canvas.parentElement.getBoundingClientRect();
    const isFs = !!(document.fullscreenElement || document.webkitFullscreenElement);
    // Width: body width minus horizontal padding (24 normal, 32 fullscreen).
    const hPad = isFs ? 32 : 24;
    const w = Math.max(200, bodyRect.width - hPad);
    // Height: in fullscreen let CSS stretch via calc(); else use fixed {height}.
    const h = isFs
      ? Math.max(200, window.innerHeight - 46 - 38 - 16)
      : {height};
    const dpr = window.devicePixelRatio || 1;
    canvas.width = w * dpr; canvas.height = h * dpr;
    canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw();
  }}

  function draw() {{
    const w = parseFloat(canvas.style.width);
    const h = parseFloat(canvas.style.height);
    ctx.clearRect(0, 0, w, h);
    const active = getActive();
    if (!active.length) return;

    // Visible-window slicing only applies to shared-x series; XY series
    // ignore the panel-wide visible range (their x comes from each
    // point's own xy[i][0] — slicing parallel to DATA.x would be wrong).
    const vr = visibleRange();
    const total = DATA.x.length || 0;
    const startIdx = Math.floor(vr.start * total);
    const endIdx = Math.min(Math.ceil(vr.end * total), Math.max(0, total - 1));
    const visX = total ? DATA.x.slice(startIdx, endIdx + 1) : [];
    const visSeries = active.map(s => Array.isArray(s.data)
      ? ({{ ...s, data: s.data.slice(startIdx, endIdx + 1) }})
      : s  // XY series pass through unchanged
    );

    // Whether ANY series is XY-pair mode (cross-plot: hysteresis, phase
    // space). In that mode, x comes from the series's own xy[i][0], not
    // the panel-wide visX array.
    const isGap = v => (v === null || v === undefined || Number.isNaN(v));
    const hasXY = visSeries.some(s => Array.isArray(s.xy));

    // ── Y-bounds ───────────────────────────────────────────────────────
    // Build TWO scales (left + right). Series declare their axis via
    // s.axis === "right". When no series uses right, the right-axis
    // bookkeeping collapses (right === left) and we render a normal
    // single-axis chart — no visual change vs the pre-dual-axis era.
    const computeYBounds = (axisKey) => {{
      let mn = Infinity, mx = -Infinity;
      for (const s of visSeries) {{
        if ((s.axis || 'left') !== axisKey) continue;
        if (Array.isArray(s.xy)) {{
          for (const p of s.xy) {{
            const yv = p[1];
            if (isGap(yv)) continue;
            if (yv < mn) mn = yv;
            if (yv > mx) mx = yv;
          }}
        }} else if (Array.isArray(s.data)) {{
          for (const v of s.data) {{
            if (isGap(v)) continue;
            if (v < mn) mn = v;
            if (v > mx) mx = v;
          }}
        }}
      }}
      if (mn === Infinity) {{ mn = 0; mx = 1; }}
      const r0 = (mx - mn) || 1;
      const pad = r0 * 0.08;
      return [mn - pad, mx + pad];
    }};

    const hasRightAxis = visSeries.some(s => (s.axis || 'left') === 'right');
    let [yMinL, yMaxL] = computeYBounds('left');
    let [yMinR, yMaxR] = hasRightAxis ? computeYBounds('right') : [yMinL, yMaxL];

    // Back-compat aliases — most of the existing code refers to
    // ``yMin`` / ``yMax`` / ``yRange``. Keep those pointing at the LEFT
    // axis so all the existing tooling (split-mode, hover crosshair,
    // annotations against numerical y) still works.
    let yMin = yMinL, yMax = yMaxL;
    const yRangeL = yMaxL - yMinL;
    const yRangeR = yMaxR - yMinR;
    const yRange = yRangeL;

    // X-bounds — real min/max. In XY mode, from xy[i][0] across all
    // xy series; otherwise from visX. Using visX[0]/visX[last] would
    // break non-monotonic axes (hysteresis loops, phase space) where
    // the curve revisits x positions and first/last aren't extremes.
    let xMin = Infinity, xMax = -Infinity;
    if (hasXY) {{
      for (const s of visSeries) {{
        if (!Array.isArray(s.xy)) continue;
        for (const p of s.xy) {{
          const xv = p[0];
          if (isGap(xv)) continue;
          if (xv < xMin) xMin = xv;
          if (xv > xMax) xMax = xv;
        }}
      }}
    }} else {{
      for (const v of visX) {{
        if (isGap(v)) continue;
        if (v < xMin) xMin = v;
        if (v > xMax) xMax = v;
      }}
    }}
    if (xMin === Infinity) {{ xMin = 0; xMax = 1; }}
    // Small x-padding so curve doesn't hug the axis edge.
    const xR0 = (xMax - xMin) || 1;
    const xPadV = hasXY ? xR0 * 0.04 : 0;
    xMin -= xPadV; xMax += xPadV;
    const xRange = (xMax - xMin) || 1;

    // Reserve right-side gutter for the secondary y-axis ticks + label.
    // Ratchets PAD.r upward when the chart is dual-axis; otherwise use
    // whatever PAD.r the layout pre-set.
    const padR = hasRightAxis ? Math.max(PAD.r, 56) : PAD.r;
    const cw = w - PAD.l - padR;
    const ch = h - PAD.t - PAD.b;
    const toX = v => PAD.l + ((v - xMin) / xRange) * cw;
    const toYL = v => PAD.t + ch - ((v - yMinL) / yRangeL) * ch;
    const toYR = v => PAD.t + ch - ((v - yMinR) / yRangeR) * ch;
    // Default ``toY`` keeps pointing at the left axis for any code that
    // doesn't know about dual-axis (annotations, hover crosshair).
    // Series-aware drawing routines pick toYL / toYR explicitly.
    const toY = toYL;
    const toYFor = (s) => ((s && (s.axis || 'left') === 'right') ? toYR : toYL);

    // Grid (8×10, slate 0.1 alpha, 0.5 lw — charts.jsx line 164-174)
    ctx.strokeStyle = 'rgba(148,163,184,0.1)';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 8; i++) {{
      const y = PAD.t + (ch / 8) * i;
      ctx.beginPath(); ctx.moveTo(PAD.l, y); ctx.lineTo(PAD.l + cw, y); ctx.stroke();
    }}
    for (let i = 0; i <= 10; i++) {{
      const x = PAD.l + (cw / 10) * i;
      ctx.beginPath(); ctx.moveTo(x, PAD.t); ctx.lineTo(x, PAD.t + ch); ctx.stroke();
    }}

    // Axis lines — left + bottom always. Right axis only when dual-axis.
    ctx.strokeStyle = '{BORDER}'; ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(PAD.l, PAD.t); ctx.lineTo(PAD.l, PAD.t + ch); ctx.lineTo(PAD.l + cw, PAD.t + ch);
    ctx.stroke();
    if (hasRightAxis) {{
      ctx.beginPath();
      ctx.moveTo(PAD.l + cw, PAD.t); ctx.lineTo(PAD.l + cw, PAD.t + ch);
      ctx.stroke();
    }}

    // Y ticks (shared-axis only — split mode draws per-band ticks below,
    // so we skip the panel-wide ones to avoid overlapping labels).
    if (viewMode !== 'split') {{
      ctx.fillStyle = '{TEXT_3}';
      ctx.font = "10px 'JetBrains Mono', monospace";
      // Left axis ticks
      ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
      for (let i = 0; i <= 4; i++) {{
        const val = yMinL + (yRangeL / 4) * (4 - i);
        const y = PAD.t + (ch / 4) * i;
        ctx.fillText(fmtY(val), PAD.l - 6, y + 3);
      }}
      // Right axis ticks (dual-axis charts only)
      if (hasRightAxis) {{
        ctx.textAlign = 'left';
        for (let i = 0; i <= 4; i++) {{
          const val = yMinR + (yRangeR / 4) * (4 - i);
          const y = PAD.t + (ch / 4) * i;
          ctx.fillText(fmtY(val), PAD.l + cw + 6, y + 3);
        }}
      }}
    }}
    // X ticks
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    for (let i = 0; i <= 5; i++) {{
      const val = xMin + (xRange / 5) * i;
      const x = PAD.l + (cw / 5) * i;
      ctx.fillText(fmtX(val, xRange), x, PAD.t + ch + 8);
    }}

    // Axis labels — textBaseline 'bottom' for the X label so it sits
    // ABOVE y = h-6 (grows upward, never clips the canvas bottom).
    ctx.fillStyle = '{TEXT_2}';
    ctx.font = "10px 'DM Sans', sans-serif";
    if (DATA.xLabel) {{
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';
      ctx.fillText(DATA.xLabel, PAD.l + cw / 2, h - 6);
    }}
    if (DATA.yLabel) {{
      ctx.save(); ctx.translate(12, PAD.t + ch / 2); ctx.rotate(-Math.PI / 2);
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(DATA.yLabel, 0, 0); ctx.restore();
    }}
    if (DATA.yLabelRight && hasRightAxis) {{
      // Mirror the left label on the far right edge, rotated +90° so it
      // reads bottom-up — same convention as the left side.
      ctx.save();
      ctx.translate(w - 12, PAD.t + ch / 2);
      ctx.rotate(Math.PI / 2);
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(DATA.yLabelRight, 0, 0);
      ctx.restore();
    }}

    // XY-pair drawer (declared up-front, before the loop that uses it —
    // avoids any function-hoisting ambiguity inside the for-of body).
    // Honours s.plot: 'scatter' draws unconnected dots (right for
    // correlation scatter where adjacent points are NOT temporally
    // ordered); anything else strokes a connected polyline.
    const drawXYSeries = (s) => {{
      const plot = s.plot || 'line';
      if (plot === 'scatter') {{
        ctx.fillStyle = hexA(s.color, 0.65);
        ctx.strokeStyle = s.color;
        ctx.lineWidth = 0.8;
        for (const p of s.xy) {{
          const xv = p[0], yv = p[1];
          if (isGap(xv) || isGap(yv)) continue;
          const x = toX(xv), y = toY(yv);
          ctx.beginPath();
          ctx.arc(x, y, 2.4, 0, Math.PI * 2);
          ctx.fill();
        }}
        return;
      }}
      ctx.strokeStyle = s.color;
      ctx.lineWidth = s.dashed ? 1.3 : 1.6;
      ctx.lineJoin = 'round';
      ctx.setLineDash(s.dashed ? [4, 3] : []);
      ctx.beginPath();
      let penDown = false;
      for (const p of s.xy) {{
        const xv = p[0], yv = p[1];
        if (isGap(xv) || isGap(yv)) {{ penDown = false; continue; }}
        const x = toX(xv), y = toY(yv);
        if (!penDown) {{ ctx.moveTo(x, y); penDown = true; }}
        else ctx.lineTo(x, y);
      }}
      ctx.stroke();
      ctx.setLineDash([]);
    }};

    // ── Split mode — each shared-x series in its own band ──────────────────
    // Bypasses the normal series loop. Each band gets its own y-scale
    // so small-range traces don't get squashed when plotted next to a
    // large-range sibling.
    const splitSeries = visSeries.filter(s => Array.isArray(s.data));
    if (viewMode === 'split' && splitSeries.length >= 1) {{
      const bandGap = 14;
      const nBands = splitSeries.length;
      const bandH = Math.max(24, (ch - (nBands - 1) * bandGap) / nBands);

      splitSeries.forEach((s, idx) => {{
        const bandTop = PAD.t + idx * (bandH + bandGap);
        const bandBot = bandTop + bandH;

        // Per-band y-bounds (skip null gaps)
        let bMin = Infinity, bMax = -Infinity;
        for (const v of s.data) {{
          if (isGap(v)) continue;
          if (v < bMin) bMin = v; if (v > bMax) bMax = v;
        }}
        if (bMin === Infinity) {{ bMin = 0; bMax = 1; }}
        const bR = (bMax - bMin) || 1;
        bMin -= bR * 0.1; bMax += bR * 0.1;
        const toY_b = v => bandBot - ((v - bMin) / (bMax - bMin)) * bandH;

        // Band gridlines (3 horizontal) — lighter than main grid.
        ctx.strokeStyle = 'rgba(148,163,184,0.08)';
        ctx.lineWidth = 0.5;
        for (let g = 0; g <= 3; g++) {{
          const y = bandTop + (bandH / 3) * g;
          ctx.beginPath(); ctx.moveTo(PAD.l, y); ctx.lineTo(PAD.l + cw, y); ctx.stroke();
        }}
        // Band Y ticks (3 labels)
        ctx.fillStyle = '{TEXT_3}';
        ctx.font = "9px 'JetBrains Mono', monospace";
        ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
        for (let g = 0; g <= 2; g++) {{
          const val = bMin + (bMax - bMin) * (2 - g) / 2;
          const y = bandTop + (bandH / 2) * g;
          ctx.fillText(fmtY(val), PAD.l - 6, y + 3);
        }}
        // Band axis line (left edge of band)
        ctx.strokeStyle = '{BORDER}';
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(PAD.l, bandTop); ctx.lineTo(PAD.l, bandBot); ctx.stroke();

        // Series name chip in top-left of band
        ctx.fillStyle = s.color;
        ctx.font = "600 10px 'DM Sans', sans-serif";
        ctx.textAlign = 'left'; ctx.textBaseline = 'top';
        ctx.fillText(s.label, PAD.l + 6, bandTop + 4);

        // Line stroke
        ctx.strokeStyle = s.color;
        ctx.lineWidth = s.dashed ? 1.2 : 1.6;
        ctx.lineJoin = 'round';
        ctx.setLineDash(s.dashed ? [4, 3] : []);
        ctx.beginPath();
        let penDown = false;
        for (let j = 0; j < s.data.length; j++) {{
          if (isGap(s.data[j])) {{ penDown = false; continue; }}
          const px = toX(visX[j]);
          const py = toY_b(s.data[j]);
          if (!penDown) {{ ctx.moveTo(px, py); penDown = true; }}
          else ctx.lineTo(px, py);
        }}
        ctx.stroke();
        ctx.setLineDash([]);
      }});

      // Skip the normal series loop + hover dots — they'd draw against
      // the global y-range which doesn't exist in split mode.
      return;
    }}

    // Series — `null` values treated as pen-up gaps. XY-pair series
    // (s.xy) get drawn point-by-point; shared-x series (s.data) get
    // drawn against visX[i]. Each series picks its own y-mapper so
    // dual-axis charts route series to the correct vertical scale.
    for (const s of visSeries) {{
      if (Array.isArray(s.xy)) {{
        drawXYSeries(s);
        continue;
      }}
      const n = s.data.length;
      const plot = s.plot || 'line';
      const _toY = toYFor(s);

      // ── Scatter — dots only, no connecting line ──────────────────────────
      if (plot === 'scatter') {{
        ctx.fillStyle = s.color;
        for (let i = 0; i < n; i++) {{
          if (isGap(s.data[i])) continue;
          const x = toX(visX[i]);
          const y = _toY(s.data[i]);
          ctx.beginPath();
          ctx.arc(x, y, 2.4, 0, Math.PI * 2);
          ctx.fill();
        }}
        continue;
      }}

      // ── Bar — vertical rectangles from y=0 to each value ────────────────
      if (plot === 'bar') {{
        // Bar width: split the plot width into n slots, use ~75% of each.
        const barW = Math.max(1, (cw / n) * 0.75);
        ctx.fillStyle = hexA(s.color, 0.75);
        const zeroY = _toY(0);
        for (let i = 0; i < n; i++) {{
          if (isGap(s.data[i])) continue;
          const cx = toX(visX[i]);
          const topY = _toY(s.data[i]);
          const bw = barW;
          const bx = cx - bw / 2;
          const by = Math.min(topY, zeroY);
          const bh = Math.abs(topY - zeroY);
          ctx.fillRect(bx, by, bw, Math.max(1, bh));
        }}
        // Subtle stroke on top edge of each bar
        ctx.strokeStyle = s.color;
        ctx.lineWidth = 1;
        continue;
      }}

      // ── Line / Area (default) ───────────────────────────────────────────
      // Filled area under the line — draw as one closed polygon per
      // contiguous non-null segment. Stacked view mode forces a fill
      // on every series (overrides series-level filled=false).
      const wantFill = (viewMode === 'stacked') || (s.filled !== false);
      if (wantFill) {{
        const grad = ctx.createLinearGradient(0, PAD.t, 0, PAD.t + ch);
        grad.addColorStop(0, hexA(s.color, 0.25));
        grad.addColorStop(1, hexA(s.color, 0.02));
        ctx.fillStyle = grad;
        let segStart = -1;
        for (let i = 0; i < n; i++) {{
          if (!isGap(s.data[i])) {{
            if (segStart < 0) segStart = i;
          }} else if (segStart >= 0) {{
            _fillSeg(segStart, i - 1);
            segStart = -1;
          }}
        }}
        if (segStart >= 0) _fillSeg(segStart, n - 1);
      }}
      function _fillSeg(a, b) {{
        ctx.beginPath();
        ctx.moveTo(toX(visX[a]), PAD.t + ch);
        for (let i = a; i <= b; i++) ctx.lineTo(toX(visX[i]), _toY(s.data[i]));
        ctx.lineTo(toX(visX[b]), PAD.t + ch);
        ctx.closePath(); ctx.fill();
      }}

      // Line stroke — lift the pen on gaps, drop it again on the next
      // valid point.
      ctx.strokeStyle = s.color;
      ctx.lineWidth = s.dashed ? 1.2 : 1.6;
      ctx.lineJoin = 'round';
      ctx.setLineDash(s.dashed ? [4, 3] : []);
      ctx.beginPath();
      let penDown = false;
      for (let i = 0; i < n; i++) {{
        if (isGap(s.data[i])) {{ penDown = false; continue; }}
        const x = toX(visX[i]);
        const y = _toY(s.data[i]);
        if (!penDown) {{ ctx.moveTo(x, y); penDown = true; }}
        else ctx.lineTo(x, y);
      }}
      ctx.stroke();
      ctx.setLineDash([]);
    }}

    // ── Annotations (points, vlines) ──────────────────────────────────────
    // Drawn AFTER series and BEFORE hover, so markers sit on top of the
    // line but hover dots still dominate when the cursor is near.
    const annotations = DATA.annotations || [];
    for (const ann of annotations) {{
      if (ann.type === 'point') {{
        // Skip if x is outside visible window.
        if (ann.x < xMin || ann.x > xMax) continue;
        const px = toX(ann.x);
        const py = toY(ann.y);
        const col = ann.color || '{ACCENT}';
        ctx.fillStyle = col;
        if (ann.shape === 'diamond') {{
          ctx.save(); ctx.translate(px, py); ctx.rotate(Math.PI / 4);
          ctx.fillRect(-5, -5, 10, 10);
          ctx.restore();
        }} else {{
          ctx.beginPath(); ctx.arc(px, py, 5, 0, Math.PI * 2); ctx.fill();
          ctx.strokeStyle = '{SURFACE}'; ctx.lineWidth = 1.5; ctx.stroke();
        }}
        if (ann.label) {{
          ctx.fillStyle = col;
          ctx.font = "bold 10px 'DM Sans', sans-serif";
          const offset = ann.label_offset || 'top';
          if (offset === 'right') {{
            ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
            ctx.fillText(ann.label, px + 9, py);
          }} else if (offset === 'left') {{
            ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
            ctx.fillText(ann.label, px - 9, py);
          }} else if (offset === 'bottom') {{
            ctx.textAlign = 'center'; ctx.textBaseline = 'top';
            ctx.fillText(ann.label, px, py + 9);
          }} else {{
            ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
            ctx.fillText(ann.label, px, py - 9);
          }}
        }}
      }} else if (ann.type === 'vline') {{
        if (ann.x < xMin || ann.x > xMax) continue;
        const px = toX(ann.x);
        const col = ann.color || '#ef4444';
        ctx.strokeStyle = col;
        ctx.lineWidth = 1.2;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        ctx.moveTo(px, PAD.t);
        ctx.lineTo(px, PAD.t + ch);
        ctx.stroke();
        ctx.setLineDash([]);
        if (ann.label) {{
          ctx.fillStyle = col;
          ctx.font = "bold 10px 'DM Sans', sans-serif";
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          ctx.fillText(ann.label, px, PAD.t + 2);
        }}
      }} else if (ann.type === 'hline') {{
        const py = toY(ann.y);
        const col = ann.color || '#94a3b8';
        ctx.strokeStyle = col;
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(PAD.l, py);
        ctx.lineTo(PAD.l + cw, py);
        ctx.stroke();
        ctx.setLineDash([]);
      }}
    }}

    // XY-mode hover: crosshair lines + highlighted point at the nearest
    // cross-plot sample. Dot uses the series color with a white halo
    // (matches time-series style).
    if (hoverXY !== null) {{
      const xp = toX(hoverXY.x);
      const yp = toY(hoverXY.y);
      ctx.strokeStyle = 'rgba(148,163,184,0.2)';
      ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(xp, PAD.t); ctx.lineTo(xp, PAD.t + ch);
      ctx.moveTo(PAD.l, yp); ctx.lineTo(PAD.l + cw, yp);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = hoverXY.series.color;
      ctx.beginPath(); ctx.arc(xp, yp, 5, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = '{SURFACE}'; ctx.lineWidth = 2; ctx.stroke();
    }}

    // Hover crosshair + dots
    if (hover !== null && hover >= 0 && hover < visX.length) {{
      const xp = toX(visX[hover]);
      ctx.strokeStyle = 'rgba(148,163,184,0.2)';
      ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(xp, PAD.t); ctx.lineTo(xp, PAD.t + ch); ctx.stroke();

      // Horizontal crosshair pinned to first visible series. Use that
      // series's own y-mapper so dual-axis charts don't draw a crosshair
      // at a position that disagrees with where the dot lands.
      const refSeries = visSeries.find(s => Array.isArray(s.data));
      if (refSeries && !isGap(refSeries.data[hover])) {{
        const yp0 = toYFor(refSeries)(refSeries.data[hover]);
        ctx.strokeStyle = 'rgba(148,163,184,0.12)';
        ctx.beginPath(); ctx.moveTo(PAD.l, yp0); ctx.lineTo(PAD.l + cw, yp0); ctx.stroke();
      }}
      ctx.setLineDash([]);

      for (const s of visSeries) {{
        if (!Array.isArray(s.data)) continue;
        const vv = s.data[hover];
        if (isGap(vv)) continue;  // skip series without a value at this x
        const y = toYFor(s)(vv);
        ctx.fillStyle = s.color;
        ctx.beginPath(); ctx.arc(xp, y, 4, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '{SURFACE}'; ctx.lineWidth = 2; ctx.stroke();
      }}
    }}

    // Selection box (box-zoom)
    if (selectionBox) {{
      const sx = PAD.l + selectionBox.start * cw;
      const ex = PAD.l + selectionBox.end * cw;
      ctx.fillStyle = 'rgba(16,185,129,0.10)';
      ctx.fillRect(sx, PAD.t, ex - sx, ch);
      ctx.strokeStyle = '{ACCENT}'; ctx.lineWidth = 1;
      ctx.setLineDash([4, 2]); ctx.strokeRect(sx, PAD.t, ex - sx, ch); ctx.setLineDash([]);
    }}
  }}

  // Mouse interaction
  const getNorm = e => {{
    const rect = canvas.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const cw = rect.width - PAD.l - PAD.r;
    return Math.max(0, Math.min(1, (px - PAD.l) / cw));
  }};

  canvas.addEventListener('mousedown', e => {{
    if (e.button !== 0) return;
    isDragging = true; dragStart = getNorm(e); selectionBox = null;
  }});

  canvas.addEventListener('mousemove', e => {{
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const w = rect.width;
    const cw = w - PAD.l - PAD.r;
    const norm = Math.max(0, Math.min(1, (mx - PAD.l) / cw));
    const isXYPanel = getActive().some(s => Array.isArray(s.xy));

    if (isDragging && dragStart !== null) {{
      const dist = Math.abs(norm - dragStart);
      if (dist > 0.02) {{
        selectionBox = {{ start: Math.min(dragStart, norm), end: Math.max(dragStart, norm) }};
      }}
    }} else if (mx < PAD.l || mx > w - PAD.r) {{
      hover = null; hoverXY = null;
      tt.style.display = 'none'; draw(); return;
    }} else if (isXYPanel) {{
      // XY-mode hover — nearest point by Euclidean pixel distance, same
      // UX as the time-series tooltip but without the axis-index lookup
      // (cross-plot points aren't parallel to a shared x array).
      hover = null;
      const my = e.clientY - rect.top;
      hoverXY = _findNearestXY(mx, my);
      if (hoverXY) {{
        const xVal = hoverXY.x, yVal = hoverXY.y;
        const xStr = Math.abs(xVal) >= 100 ? xVal.toFixed(1) : xVal.toFixed(3);
        const yStr = Math.abs(yVal) >= 100 ? yVal.toFixed(1) : yVal.toFixed(3);
        let html = '<div class="tt-hdr">' + (DATA.xLabel || 'x') + ': ' + xStr + '</div>'
                 + '<div class="tt-row" style="margin-top:4px">'
                 + '<span class="tt-dot" style="background:' + hoverXY.series.color + '"></span>'
                 + '<span class="tt-lbl">' + hoverXY.series.label + '</span>'
                 + '<span class="tt-val">' + yStr + '</span>'
                 + '</div>';
        tt.innerHTML = html;
        tt.style.display = 'block';
        const ttW = tt.offsetWidth;
        if ((mx + ttW + 24) < w) {{ tt.style.left = (mx + 14) + 'px'; tt.style.right = ''; }}
        else {{ tt.style.right = (w - mx + 14) + 'px'; tt.style.left = ''; }}
        tt.style.top = Math.max(8, Math.min(my - 12, rect.height - 80)) + 'px';
      }} else {{
        tt.style.display = 'none';
      }}
    }} else {{
      hoverXY = null;
      const vr = visibleRange();
      const total = DATA.x.length;
      const startIdx = Math.floor(vr.start * total);
      const endIdx = Math.min(Math.ceil(vr.end * total), total - 1);
      const visLen = endIdx - startIdx + 1;
      hover = Math.max(0, Math.min(Math.round(norm * (visLen - 1)), visLen - 1));

      const absIdx = startIdx + hover;
      let html = '<div class="tt-hdr">' + (DATA.xLabel || 'x') + ': ' + DATA.x[absIdx].toFixed(5) + '</div>';
      for (const s of getActive()) {{
        if (Array.isArray(s.xy)) continue;
        const v = s.data[absIdx];
        if (v === null || v === undefined || Number.isNaN(v)) continue;
        const vs = Math.abs(v) >= 100 ? v.toFixed(1) : v.toFixed(4);
        html += '<div class="tt-row"><span class="tt-dot" style="background:' + s.color + '"></span>'
             +  '<span class="tt-lbl">' + s.label + '</span>'
             +  '<span class="tt-val">' + vs + '</span></div>';
      }}
      tt.innerHTML = html; tt.style.display = 'block';
      const ttW = tt.offsetWidth;
      if ((mx + ttW + 24) < w) {{ tt.style.left = (mx + 14) + 'px'; tt.style.right = ''; }}
      else {{ tt.style.right = (w - mx + 14) + 'px'; tt.style.left = ''; }}
      tt.style.top = '16px';
    }}
    draw();
  }});

  canvas.addEventListener('mouseup', () => {{
    if (selectionBox && (selectionBox.end - selectionBox.start) > 0.02) {{
      const vr = visibleRange();
      const win = vr.end - vr.start;
      const newStart = vr.start + selectionBox.start * win;
      const newEnd = vr.start + selectionBox.end * win;
      const newWin = newEnd - newStart;
      zoom = Math.min(1 / newWin, 20); panOffset = newStart;
      updZoomLabel();
    }}
    isDragging = false; dragStart = null; selectionBox = null;
    draw();
  }});

  canvas.addEventListener('mouseleave', () => {{
    hover = null; hoverXY = null;
    isDragging = false; dragStart = null; selectionBox = null;
    tt.style.display = 'none'; draw();
  }});

  // Mousewheel zoom deliberately omitted — only the toolbar buttons
  // (+ / − / Reset / pan-left / pan-right) drive zoom/pan, so scrolling
  // the page over a chart never hijacks the wheel.

  canvas.addEventListener('dblclick', () => {{
    zoom = 1; panOffset = 0; updZoomLabel(); draw();
  }});

  // Toolbar
  const $ = q => document.querySelector(q);
  $('[data-action="zoom-in"]').addEventListener('click', () => {{
    zoom = Math.min(zoom * 1.5, 20); updZoomLabel(); draw();
  }});
  $('[data-action="zoom-out"]').addEventListener('click', () => {{
    zoom = Math.max(zoom / 1.5, 1);
    if (zoom === 1) panOffset = 0;
    updZoomLabel(); draw();
  }});
  $('[data-action="pan-left"]').addEventListener('click', () => {{
    panOffset = Math.max(0, panOffset - 0.1 / zoom); draw();
  }});
  $('[data-action="pan-right"]').addEventListener('click', () => {{
    const win = 1 / zoom;
    panOffset = Math.min(1 - win, panOffset + 0.1 / zoom); draw();
  }});
  $('[data-action="reset"]').addEventListener('click', () => {{
    zoom = 1; panOffset = 0; updZoomLabel(); draw();
  }});
  $('[data-action="fullscreen"]').addEventListener('click', () => {{
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen && document.documentElement.requestFullscreen();
    setTimeout(resize, 100);
  }});
  document.addEventListener('fullscreenchange', () => setTimeout(resize, 100));

  // Download icon (header) → PNG
  const dlBtn = document.querySelector('.icon-btn[title="Export"]');
  if (dlBtn) {{
    dlBtn.addEventListener('click', () => {{
      const out = document.createElement('canvas');
      out.width = canvas.width; out.height = canvas.height;
      const octx = out.getContext('2d');
      octx.fillStyle = '{SURFACE}';
      octx.fillRect(0, 0, out.width, out.height);
      octx.drawImage(canvas, 0, 0);
      out.toBlob(blob => {{
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = '{key}_chart.png';
        document.body.appendChild(a); a.click();
        document.body.removeChild(a); URL.revokeObjectURL(url);
      }});
    }});
  }}

  // SmallBtn toggle groups
  document.querySelectorAll('.small-btn[data-group="unit"]').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('.small-btn[data-group="unit"]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      unitFactor = parseFloat(btn.getAttribute('data-factor')) || 1;
      const unit = btn.textContent.trim();
      if (DATA.yLabel) DATA.yLabel = DATA.yLabel.replace(/\\(([^)]+)\\)/, '(' + unit + ')');
      draw();
    }});
  }});
  // View-mode radio group (Overlay / Stacked) — clicking one deactivates
  // the other; the canvas re-renders with the new viewMode.
  document.querySelectorAll('.small-btn[data-group="mode"]').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('.small-btn[data-group="mode"]').forEach(
        b => b.classList.remove('active')
      );
      btn.classList.add('active');
      viewMode = btn.getAttribute('data-mode') || 'overlay';
      draw();
    }});
  }});

  // Trace visibility — each button is an independent toggle (Smoothed and
  // Raw can both be on at once, matching view-dashboard.jsx which draws
  // both traces simultaneously).
  document.querySelectorAll('.small-btn[data-group="trace"]').forEach(btn => {{
    btn.addEventListener('click', () => {{
      btn.classList.toggle('active');
      const target = btn.getAttribute('data-label');
      const on = btn.classList.contains('active');
      for (const s of SERIES0) {{
        if (s.label === target) s.visible = on;
      }}
      draw();
    }});
  }});

  // Pick up initial active toggles. For "trace" group, each series' visibility
  // mirrors whether its button starts active (multi-toggle: both can be on).
  const au = document.querySelector('.small-btn.active[data-group="unit"]');
  if (au) unitFactor = parseFloat(au.getAttribute('data-factor')) || 1;
  const am = document.querySelector('.small-btn.active[data-group="mode"]');
  if (am) viewMode = am.getAttribute('data-mode') || 'overlay';
  const traceBtns = document.querySelectorAll('.small-btn[data-group="trace"]');
  if (traceBtns.length) {{
    const activeLabels = new Set();
    traceBtns.forEach(b => {{
      if (b.classList.contains('active')) activeLabels.add(b.getAttribute('data-label'));
    }});
    for (const s of SERIES0) s.visible = activeLabels.has(s.label);
  }}

  new ResizeObserver(resize).observe(canvas.parentElement);
  resize();
}})();
</script>
</body></html>"""
