"""views/_import_panels.py — Data Setup panel for the SHM dashboard.

SHM data is much simpler to map than RPLT: there's one time column
(usually called ``timestamp`` / ``time`` / ``date``) and every other
column is a sensor in its physical units (mm / ° / °C / etc.). No
need for accel-vs-load role mapping, unit conversion modes, or
derive-from-load. The user just confirms the time column.

Also surfaces a quick sensor-type breakdown — *"5 LVDTs · 3 tiltmeters
· 3 thermocouples"* — so it's obvious at a glance what was loaded.
"""
from __future__ import annotations

import html as html_mod

import streamlit as st

from lib.cache import ensure_registered, table_version
from lib.components import badge
from lib.queries import column_names
from lib.shm import classify_columns, SENSOR_TYPES
from lib.state import get_active_info


def _panel_open(key: str, title: str, right_html: str = "") -> None:
    """Card-chrome header for a Streamlit container. Style lives in
    ``assets/rgf.css`` under ``.st-key-<key> .rgf-panel-hdr``."""
    actions = f'<div class="rgf-panel-actions">{right_html}</div>'
    st.markdown(
        f'<div class="rgf-panel-hdr">'
        f'<span class="rgf-panel-title">{html_mod.escape(title)}</span>'
        f'{actions}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _pick_time_col(cols: list[str]) -> str:
    """Header-based pick for the time column. SHM CSVs typically use
    ``timestamp`` / ``time`` / ``date`` / ``datetime`` for the index;
    if the file was indexed at write time the column name might be
    blank — which DuckDB exposes as ``"column0"`` — so we look for
    that too as a final fallback.
    """
    candidates = ("timestamp", "time", "date", "datetime", "ts", "column0", "")
    low = [c.lower() for c in cols]
    for cand in candidates:
        if cand and cand in low:
            return cols[low.index(cand)]
    for cand in candidates:
        if not cand:
            continue
        for i, c in enumerate(low):
            if cand in c:
                return cols[i]
    return cols[0] if cols else ""


def render_data_setup() -> None:
    """One-row picker for the time column + a sensor-type breakdown.

    No units / role mapping — every non-time column is treated as a
    sensor in its native units. Type detection (``classify_columns``)
    drives default chart palette + grouping in the Sensor Browser.
    """
    info = get_active_info()

    if info:
        ensure_registered(info.table_name)
        v = table_version(info.table_name)
        cols = column_names(info.table_name, v) or ["—"]
    else:
        cols = ["—"]

    ss = st.session_state

    # Re-seed the time-column pick when a new file becomes active.
    current_tbl = info.table_name if info else "_none_"
    if ss.get("_shm_setup_table") != current_tbl:
        ss["_shm_setup_table"] = current_tbl
        ss["rgf_map_time"] = _pick_time_col(cols)

    ss.setdefault("rgf_map_time", cols[0])
    if ss["rgf_map_time"] not in cols:
        ss["rgf_map_time"] = cols[0]

    # Sensor columns = everything except the time column.
    sensor_cols = [c for c in cols if c != ss["rgf_map_time"]]
    type_map = classify_columns(sensor_cols) if info else {}

    with st.container(key="rgf_panel_setup"):
        _panel_open(
            "rgf_panel_setup",
            "Data Setup",
            right_html=(
                badge("Edit anytime", "blue")
                if info else badge("Load a file to begin", "gray")
            ),
        )

        c_role, c_col, c_summary = st.columns([0.85, 2.2, 3.0], gap="small")
        with c_role:
            st.markdown('<div class="rgf-setup-role">TIME</div>',
                        unsafe_allow_html=True)
        with c_col:
            st.selectbox(
                "Time column", cols,
                index=cols.index(ss["rgf_map_time"]) if ss["rgf_map_time"] in cols else 0,
                key="rgf_map_time",
                label_visibility="collapsed",
                disabled=not info,
            )
        with c_summary:
            if info and type_map:
                bits = []
                for t in SENSOR_TYPES:
                    n = len(type_map.get(t["id"], []))
                    if n:
                        bits.append(
                            f'<span class="rgf-shm-sensor-pill" '
                            f'style="--sensor-color:{t["color"]}">'
                            f'<b>{n}</b> {html_mod.escape(t["label"].split(" (")[0])}'
                            f'</span>'
                        )
                st.markdown(
                    f'<div class="rgf-shm-sensor-chips">{"".join(bits)}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="rgf-setup-stats rgf-setup-stats-empty">—</div>',
                    unsafe_allow_html=True,
                )

        if info:
            st.markdown(
                '<div style="font-size:11px;color:var(--text-3);padding-top:6px;">'
                'Time column selection flows into every view. Sensor columns '
                'are auto-classified by name (LVDT / Tiltmeter / Thermocouple / '
                'Strain / Vibrating Wire / Pressure) — drives the default '
                'chart colours and grouping on the Sensor Browser.'
                '</div>',
                unsafe_allow_html=True,
            )
