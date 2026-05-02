"""
lib/components.py — Reusable UI components.

Shared shell helpers used by every view. Styles live in assets/rgf.css
under the .rgf-* class tree.

Public:
    page_header(title, subtitle="", right_html="")  — title + subtitle + actions
    badge(text, color="green")                      — inline coloured pill
    empty_state(icon, title, message)               — centered placeholder
    section_heading(text, major=False)              — uppercase rail heading
    kpi_strip(ribbon, cells)                        — institutional KPI row
    print_panel(title, rows, *, status=None,
                hl_label=None, hl_value=None)       — right-rail K/V panel
    stat_mini(label, value, unit="")                — small left-railed metric

The KPI strip + print panel patterns are ported from the Oriel
demo (institutional finance dashboard) — same dense engineer-grade
layout, retuned to the SHM teal/dark theme.
"""
from __future__ import annotations

import html as html_mod

import streamlit as st

from lib.icons import ICONS, svg


# ── Page header ──────────────────────────────────────────────────────────────
def page_header(title: str, subtitle: str = "", right_html: str = "") -> None:
    """Render a page title + subtitle with optional right-aligned action area.

    ``right_html`` is raw HTML injected into the actions slot (e.g. badges,
    SmallBtn markup). Title/subtitle are escaped.
    """
    sub = f'<p class="rgf-pghdr-sub">{html_mod.escape(subtitle)}</p>' if subtitle else ""
    actions = f'<div class="rgf-pghdr-actions">{right_html}</div>' if right_html else ""
    st.markdown(
        f'<div class="rgf-pghdr">'
        f'<div>'
        f'<h1 class="rgf-pghdr-title">{html_mod.escape(title)}</h1>'
        f'{sub}'
        f'</div>'
        f'{actions}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Badge ────────────────────────────────────────────────────────────────────
def badge(text: str, color: str = "green") -> str:
    """Return an inline HTML pill. ``color`` ∈ {green, blue, amber, violet, cyan, gray}."""
    color_cls = f"rgf-badge-{color}" if color in {"green", "blue", "amber", "violet", "cyan", "gray"} else "rgf-badge-gray"
    return f'<span class="rgf-badge {color_cls}">{html_mod.escape(text)}</span>'


# ── Empty state ──────────────────────────────────────────────────────────────
def empty_state(icon: str, title: str, message: str) -> None:
    """Centered placeholder.

    ``icon`` resolution order:
      1. If it matches a key in ``lib.icons.ICONS`` → render as an SVG
         (stroke-only, picks up the .rgf-empty-icon colour via currentColor).
      2. Otherwise, if truthy, render the string verbatim inside the icon
         slot (emoji fallback — kept for back-compat with any legacy call).
      3. If empty → omit the icon slot entirely.
    """
    if icon in ICONS:
        inner = svg(icon, size=36)
        icon_html = f'<div class="rgf-empty-icon rgf-empty-icon-svg">{inner}</div>'
    elif icon:
        icon_html = (
            f'<div class="rgf-empty-icon">{html_mod.escape(icon)}</div>'
        )
    else:
        icon_html = ''
    st.markdown(
        f'<div class="rgf-empty-state">'
        f'{icon_html}'
        f'<div class="rgf-empty-title">{html_mod.escape(title)}</div>'
        f'<div class="rgf-empty-message">{html_mod.escape(message)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Section heading (uppercase rail) ─────────────────────────────────────────
def section_heading(text: str, *, major: bool = False) -> None:
    """Uppercase section divider with a teal left rail.

    Use ABOVE a chart-and-stats row to introduce a logical section
    ("SENSOR FAMILIES", "DRIFT DIAGNOSTICS", etc.). Ported from the
    Oriel ``shdr`` pattern for a desk / engineering feel.
    """
    cls = "rgf-shdr" + (" rgf-shdr-major" if major else "")
    st.markdown(
        f'<div class="{cls}">{html_mod.escape(text)}</div>',
        unsafe_allow_html=True,
    )


# ── KPI strip (ribbon + cell row) ───────────────────────────────────────────
def kpi_strip(ribbon: str, cells: list[dict]) -> None:
    """Institutional KPI row — uppercase ribbon over a horizontal cell rail.

    ``cells`` is a list of dicts with keys:
      - ``label``  (str)             — uppercase micro-label
      - ``value``  (str)             — primary value (mono-spaced)
      - ``unit``   (str, optional)   — e.g. ``"days"`` / ``"mm"`` / ``"%"``
      - ``sub``    (str, optional)   — secondary line below the value
      - ``lead``   (bool, optional)  — render the value larger + accent-coloured
      - ``signal`` (str, optional)   — ``"pos"`` / ``"neg"`` / ``"warn"`` to
                                       tint the value
    """
    inner_cells: list[str] = []
    for c in cells:
        cls = "rgf-kpi-cell"
        val_cls = "rgf-kpi-value"
        if c.get("lead"):
            val_cls += " rgf-kpi-value-lead"
        sig = c.get("signal")
        if sig in ("pos", "neg", "warn"):
            val_cls += f" rgf-kpi-value-{sig}"
        unit_html = (
            f'<span class="rgf-kpi-cell-unit">{html_mod.escape(c["unit"])}</span>'
            if c.get("unit") else ""
        )
        sub_html = (
            f'<div class="rgf-kpi-cell-sub">{html_mod.escape(c["sub"])}</div>'
            if c.get("sub") else ""
        )
        inner_cells.append(
            f'<div class="{cls}">'
            f'<div class="rgf-kpi-cell-micro">{html_mod.escape(c["label"])}</div>'
            f'<div class="{val_cls}">{html_mod.escape(c["value"])}{unit_html}</div>'
            f'{sub_html}'
            f'</div>'
        )
    ribbon_html = (
        f'<div class="rgf-kpi-ribbon">{html_mod.escape(ribbon)}</div>'
        if ribbon else ""
    )
    st.markdown(
        f'<div class="rgf-kpi-strip-wrap">'
        f'{ribbon_html}'
        f'<div class="rgf-kpi-strip">{"".join(inner_cells)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Print panel (right-rail key / value summary) ─────────────────────────────
def print_panel(
    title: str,
    rows: list[tuple[str, str]],
    *,
    status: str | None = None,
    hl_label: str | None = None,
    hl_value: str | None = None,
) -> None:
    """Right-rail panel — title bar + optional hero highlight + K/V rows.

    Mirrors the Oriel "index print" panel: a header with the title and
    a status chip, an optional highlight band (big number with caption),
    then a stack of ``KEY ··· VALUE`` rows for diagnostics.

    Use it next to a chart to show per-sensor stats, or by itself to
    summarise a calculation (slope, drift, anomaly count).
    """
    status_html = (
        f'<span class="rgf-ip-status">{html_mod.escape(status)}</span>'
        if status else ""
    )
    hl_html = ""
    if hl_label or hl_value:
        hl_html = (
            f'<div class="rgf-ip-hl">'
            f'<div class="rgf-ip-hl-lbl">{html_mod.escape(hl_label or "")}</div>'
            f'<div class="rgf-ip-hl-val">{html_mod.escape(hl_value or "")}</div>'
            f'</div>'
        )
    rows_html = "".join(
        f'<div class="rgf-ip-row">'
        f'<span class="rgf-ip-key">{html_mod.escape(k)}</span>'
        f'<span class="rgf-ip-val">{html_mod.escape(v)}</span>'
        f'</div>'
        for k, v in rows
    )
    st.markdown(
        f'<div class="rgf-ip-wrap">'
        f'<div class="rgf-ip-hdr">'
        f'<span class="rgf-ip-title">{html_mod.escape(title)}</span>'
        f'{status_html}'
        f'</div>'
        f'{hl_html}'
        f'<div class="rgf-ip-body">{rows_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Stat mini (small left-railed metric) ─────────────────────────────────────
def stat_mini(label: str, value: str, unit: str = "") -> str:
    """Return HTML for a small left-railed metric chip.

    Use as a building block in a ``st.markdown`` flex grid to show
    per-sensor stats inline under a chart (min · max · σ · drift · …).
    """
    unit_html = (
        f'<span class="rgf-stat-mini-unit">{html_mod.escape(unit)}</span>'
        if unit else ""
    )
    return (
        f'<div class="rgf-stat-mini">'
        f'<div class="rgf-stat-mini-lbl">{html_mod.escape(label)}</div>'
        f'<div class="rgf-stat-mini-val">{html_mod.escape(value)}{unit_html}</div>'
        f'</div>'
    )
