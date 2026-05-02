"""Raw Data view — searchable / filterable / exportable sample table.

SHM dataset table viewer. Columns are sensor readings + the time
index; user can search across any column, paginate, and export
the (search-filtered) result as CSV.
"""
from __future__ import annotations

import html as html_mod

import numpy as np
import pandas as pd
import streamlit as st

from lib.cache import ensure_registered, table_version
from lib.components import empty_state, page_header
from lib.queries import column_names
from lib.shm import get_active_dataset
from lib.state import get_active_info


_PAGE_SIZE = 20


def render() -> None:
    info = get_active_info()
    if not info:
        page_header("Raw Data", "Sensor readings — search / paginate / export")
        empty_state(
            "database", "No active dataset",
            "Import a file (or click Load Demo Dataset) to browse its rows.",
        )
        return

    ensure_registered(info.table_name)
    v = table_version(info.table_name)
    cols = column_names(info.table_name, v) or []
    if not cols:
        page_header("Raw Data", info.source_filename or info.table_name)
        empty_state("alert", "No columns",
                    "Active table has no readable columns.")
        return

    df_full = get_active_dataset()
    if df_full is None or df_full.empty:
        page_header("Raw Data", info.source_filename or info.table_name)
        empty_state("alert", "Couldn't load dataset", "")
        return

    # Display frame: keep the time index visible as a column called
    # ``timestamp`` so search/filter/export all see it.
    df = df_full.reset_index()
    if df.columns[0] in (None, "") or df.columns[0] == 0:
        df = df.rename(columns={df.columns[0]: "timestamp"})

    ss = st.session_state
    ss.setdefault("rd_search", "")
    ss.setdefault("rd_page", 1)

    _render_header_row(info, df)

    df_view = _apply_search(df, ss["rd_search"])
    if df_view.empty:
        empty_state("inbox", "No matching rows",
                    "Widen the search string or clear the filter.")
        return

    _render_data_panel(df_view)


# ── Header (search + export) ────────────────────────────────────────────────
def _render_header_row(info, df_full: pd.DataFrame) -> None:
    ss = st.session_state

    # Hidden export trigger
    csv_bytes = _apply_search(df_full, ss["rd_search"]).to_csv(index=False).encode("utf-8")
    st.download_button(
        "·", data=csv_bytes,
        file_name=f"{info.table_name}_filtered.csv",
        mime="text/csv", key="__rd_export_csv",
    )

    with st.container(key="rgf_rd_header"):
        c_title, c_search, c_actions = st.columns([2.5, 3, 1.0], gap="small")
        with c_title:
            st.markdown(
                '<div>'
                '<div class="rgf-pghdr-title">Raw Data</div>'
                f'<div class="rgf-pghdr-sub">{len(df_full):,} rows · '
                f'{df_full.shape[1]} columns</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        with c_search:
            ss["rd_search"] = st.text_input(
                "Search", value=ss.get("rd_search", ""),
                placeholder="Search across all columns…",
                key="rd_search_inp",
                label_visibility="collapsed",
            )
        with c_actions:
            st.markdown(
                '<div class="rgf-rd-icon-row">'
                '<button type="button" class="rgf-btn-icon" '
                'data-action="rd-export-csv" title="Export CSV">'
                '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" '
                'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
                'stroke-linejoin="round">'
                '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
                '<path d="M7 10l5 5 5-5"/><path d="M12 15V3"/>'
                '</svg></button>'
                '</div>',
                unsafe_allow_html=True,
            )


# ── Search filter ───────────────────────────────────────────────────────────
def _apply_search(df: pd.DataFrame, q: str) -> pd.DataFrame:
    q = (q or "").strip()
    if not q:
        return df
    needles = [n.strip() for n in q.split() if n.strip()]
    if not needles:
        return df
    str_df = df.astype(str)
    mask = pd.Series(True, index=df.index)
    for n in needles:
        mask &= str_df.apply(lambda s: s.str.contains(n, case=False, na=False)).any(axis=1)
    return df[mask]


# ── Data table + pagination ─────────────────────────────────────────────────
def _render_data_panel(df: pd.DataFrame) -> None:
    ss = st.session_state
    total_rows = len(df)
    total_pages = max(1, (total_rows + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = max(1, min(int(ss.get("rd_page", 1)), total_pages))
    ss["rd_page"] = page

    start = (page - 1) * _PAGE_SIZE
    end = min(start + _PAGE_SIZE, total_rows)
    window = df.iloc[start:end]

    # Hidden page-buttons
    for p in range(1, total_pages + 1):
        if st.button("·", key=f"__rd_page_{p}"):
            ss["rd_page"] = p
            st.rerun()
    for action in ("prev", "next"):
        if st.button("·", key=f"__rd_page_{action}"):
            delta = -1 if action == "prev" else 1
            ss["rd_page"] = max(1, min(total_pages, page + delta))
            st.rerun()

    header_cells = ('<th class="rgf-rd-rownum">#</th>'
                    + "".join(f'<th>{html_mod.escape(str(c))}</th>'
                              for c in window.columns))
    rows = []
    for local_idx, (_orig_idx, row) in enumerate(window.iterrows(), start=start + 1):
        cells = [f'<td class="rgf-rd-rownum">{local_idx}</td>']
        for col, val in zip(window.columns, row):
            cells.append(f'<td>{_fmt_cell(val)}</td>')
        cls = "rgf-rd-row" + (" alt" if local_idx % 2 == 0 else "")
        rows.append(f'<tr class="{cls}">{"".join(cells)}</tr>')

    with st.container(key="rgf_panel_rd"):
        st.markdown(
            '<div class="rgf-panel-hdr"><span class="rgf-panel-title">'
            f'Sample Data</span><span class="rgf-table-meta">'
            f'{total_rows:,} rows match · page {page}/{total_pages}</span></div>'
            '<div class="rgf-rd-table-wrap">'
            f'<table class="rgf-rd-table"><thead><tr>{header_cells}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
            f'{_pagination_html(page, total_pages, start, end, total_rows)}',
            unsafe_allow_html=True,
        )


def _fmt_cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        if not np.isfinite(v):
            return ""
        return f"{v:,.4f}" if abs(v) < 1e6 else f"{v:.3g}"
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return html_mod.escape(str(v))


def _pagination_html(page: int, total_pages: int,
                     start: int, end: int, total_rows: int) -> str:
    btns: list[str] = []
    btns.append(
        f'<button type="button" class="rgf-btn-sm" data-rd-page="prev"'
        f'{" disabled" if page == 1 else ""}>Prev</button>'
    )
    # Compact page numbers: first 2, current ±1, last 2
    shown: set = {1, total_pages, page, page - 1, page + 1, 2, total_pages - 1}
    shown = {p for p in shown if 1 <= p <= total_pages}
    last = 0
    for p in sorted(shown):
        if last and p - last > 1:
            btns.append('<span class="rgf-rd-ellipsis">…</span>')
        btns.append(
            f'<button type="button" class="rgf-btn-sm'
            f'{" active" if p == page else ""}" '
            f'data-rd-page="{p}">{p}</button>'
        )
        last = p
    btns.append(
        f'<button type="button" class="rgf-btn-sm" data-rd-page="next"'
        f'{" disabled" if page == total_pages else ""}>Next</button>'
    )
    return (
        '<div class="rgf-rd-pagination">'
        f'<span class="rgf-rd-pagination-info">'
        f'Showing {start + 1:,}–{end:,} of {total_rows:,}'
        '</span>'
        f'<div class="rgf-rd-pagination-btns">{"".join(btns)}</div>'
        '</div>'
    )
