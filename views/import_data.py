"""Import Data view — file upload + bundled demo loader, simplified
for SHM (no Google Sheets / GCP source tabs — those were RPLT-side
mocks that don't exist here yet).

The upload flow uses the same streaming-to-Parquet pipeline as the
RPLT app — DuckDB's ``read_csv_auto`` handles the SHM CSV with its
standard ``timestamp,LVDT1,LVDT2,…`` header without further config.
"""
from __future__ import annotations

import html as html_mod
import os
import time

import pandas as pd
import streamlit as st

from lib.cache import ensure_registered, table_version
from lib.components import badge, empty_state, page_header
from lib.icons import svg
from lib.ingest import (
    ingest_file, list_excel_sheets, load_metadata, resolve_demo_ingest_path,
)
from lib.queries import head
from lib.sources import gsheet, manual
from lib.state import (
    add_imported, get_active_info, get_active_table,
    imported_tables, remove_imported, session_id, set_active_table,
)
from views._import_panels import _panel_open, render_data_setup


# ── Main render ──────────────────────────────────────────────────────────────
def render() -> None:
    # Hidden file-row activation
    for tname in imported_tables():
        if st.button("·", key=f"__activate_{tname}"):
            set_active_table(tname)
            st.rerun()

    # Hidden Clear All trigger
    if st.button("·", key="__clear_all_files"):
        for tname in list(imported_tables()):
            remove_imported(tname)
        st.rerun()

    # Hidden Load Demo trigger
    if st.button("·", key="__load_demo"):
        _load_demo()

    page_header(
        "Import Data",
        "Upload a CSV / Parquet of long-term sensor readings",
    )

    _render_upload()
    _render_gsheet_source()
    render_data_setup()
    _render_file_list()
    _render_data_preview()


def _load_demo() -> None:
    sid = session_id()
    try:
        src_path = resolve_demo_ingest_path(sid)
        result = ingest_file(src_path, sid, sheet_name=None)
    except Exception as exc:
        st.error(f"Demo load failed: {exc}")
    else:
        add_imported(result.table_name)
        set_active_table(result.table_name)
        st.rerun()


# ── File Upload ──────────────────────────────────────────────────────────────
def _render_upload() -> None:
    with st.container(key="rgf_upload_shell"):
        uploaded = st.file_uploader(
            "upload",
            type=manual.SUPPORTED_EXTENSIONS,
            accept_multiple_files=False,
            label_visibility="collapsed",
            key="rgf_import_upload",
        )
        st.markdown(
            f'''
            <div class="rgf-drop-overlay">
              <div class="rgf-drop-icon">{svg("upload", size=24, color="#10b981")}</div>
              <div class="rgf-drop-title">Drop SHM data here or click to browse</div>
              <div class="rgf-drop-sub">Supports .csv, .xlsx, .txt, .parquet — up to 2 GB</div>
            </div>
            ''',
            unsafe_allow_html=True,
        )
    if uploaded is not None:
        _process_uploaded(uploaded)


# ── Google Sheets source ────────────────────────────────────────────────────
def _render_gsheet_source() -> None:
    """Expandable 'From Google Sheets' section under the file uploader.

    Accepts any Sheets URL whose sharing is at least 'Anyone with the
    link · Viewer' (or a Publish-to-web CSV link). The download path
    in ``lib/sources/gsheet.py`` does NOT require a service account —
    the same Cloud Run image works without IAM changes.
    """
    with st.expander("Or load from a Google Sheets URL"):
        st.markdown(
            '<div class="rgf-gsheet-help">'
            'Paste a Google Sheets link. Sharing must be set to '
            '<strong>Anyone with the link · Viewer</strong> '
            '— or use <em>File → Share → Publish to web (CSV)</em>. '
            'For private sheets, host them on the same project and '
            'grant the Cloud Run service account read access.'
            '</div>',
            unsafe_allow_html=True,
        )
        url = st.text_input(
            "Sheet URL",
            key="rgf_gsheet_url",
            placeholder="https://docs.google.com/spreadsheets/d/.../edit?gid=0",
            label_visibility="collapsed",
        )
        c1, c2 = st.columns([1, 4])
        with c1:
            fetch_clicked = st.button(
                "Fetch", type="primary", key="rgf_gsheet_fetch_btn",
                use_container_width=True,
            )
        with c2:
            if url:
                try:
                    sid_, gid_ = gsheet.parse_url(url)
                    st.markdown(
                        f'<div class="rgf-gsheet-parsed">'
                        f'<span>Sheet&nbsp;<code>{html_mod.escape(sid_[:14])}…</code></span>'
                        + (f'<span>· Tab gid <code>{gid_}</code></span>' if gid_ else "")
                        + '</div>',
                        unsafe_allow_html=True,
                    )
                except ValueError:
                    pass

        if not fetch_clicked or not url:
            return
        sid = session_id()
        try:
            src_path = gsheet.fetch_to_disk(url, sid)
            result = ingest_file(src_path, sid, sheet_name=None)
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
            return
        except Exception as exc:  # surface any other ingestion error verbatim
            st.error(f"Import failed: {exc}")
            return
        add_imported(result.table_name)
        set_active_table(result.table_name)
        st.rerun()


def _process_uploaded(uploaded) -> None:
    sid = session_id()
    src_path = manual.save(uploaded, sid)
    kb = src_path.stat().st_size / 1024
    st.markdown(
        f'<div class="rgf-upload-hint">'
        f'<span><strong>{html_mod.escape(uploaded.name)}</strong> &nbsp;·&nbsp; '
        f'{kb:,.0f} KB ready to import</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    sheet_name = None
    if src_path.suffix.lower() in (".xlsx", ".xls"):
        sheets = list_excel_sheets(src_path)
        if len(sheets) > 1:
            sheet_name = st.selectbox("Sheet", sheets, index=0, key="rgf_import_sheet")
        else:
            sheet_name = sheets[0]
    if st.button("Import Dataset", type="primary", key="rgf_import_btn"):
        try:
            result = ingest_file(src_path, sid, sheet_name=sheet_name)
        except Exception as exc:
            st.error(f"Import failed: {exc}")
        else:
            add_imported(result.table_name)
            set_active_table(result.table_name)
            st.rerun()


# ── Imported Files list ──────────────────────────────────────────────────────
def _render_file_list() -> None:
    tables = imported_tables()
    active = get_active_table()

    right_html = ""
    if tables:
        right_html = (
            '<button type="button" class="rgf-btn-sm" data-clear="all">Clear All</button>'
        )

    with st.container(key="rgf_panel_files"):
        _panel_open("rgf_panel_files", "Imported Datasets", right_html=right_html)
        if not tables:
            _render_files_empty()
        else:
            rows = []
            for tname in tables:
                info = load_metadata(tname)
                if info is None:
                    continue
                is_active = tname == active
                size_str = _format_size(info.parquet_path)
                date_str = _format_date(info.ingested_at)
                status_html = (badge("Active", "green") if is_active
                               else badge("Imported", "gray"))
                rows.append(
                    f'<button type="button" class="rgf-file-row" '
                    f'data-activate="{tname}">'
                    f'<div class="rgf-file-ico rgf-file-ico-upload">{svg("report", size=18)}</div>'
                    f'<div style="flex:1; min-width:0; text-align:left;">'
                    f'<div class="rgf-file-name">'
                    f'{html_mod.escape(info.source_filename or info.table_name)}</div>'
                    f'<div class="rgf-file-meta">'
                    f'{size_str} · {info.row_count:,} rows · {info.column_count} cols · {date_str}'
                    f'<span class="rgf-file-src-chip">File</span>'
                    f'</div>'
                    f'</div>'
                    f'{status_html}'
                    f'</button>'
                )
            st.markdown("\n".join(rows), unsafe_allow_html=True)


def _render_files_empty() -> None:
    st.markdown(
        f'<div class="rgf-files-empty">'
        f'<div class="rgf-files-empty-icon">{svg("folder", size=32)}</div>'
        '<div class="rgf-files-empty-title">No datasets imported yet</div>'
        '<div class="rgf-files-empty-msg">Upload a file above, or try the demo dataset below.</div>'
        '<button type="button" class="rgf-btn-primary" data-action="load-demo">'
        'Load Demo Dataset</button>'
        '</div>',
        unsafe_allow_html=True,
    )


def _format_size(path_str: str) -> str:
    try:
        sz = os.path.getsize(path_str)
    except OSError:
        return "—"
    if sz < 1024:
        return f"{sz} B"
    if sz < 1024 * 1024:
        return f"{sz / 1024:.0f} KB"
    return f"{sz / 1024 / 1024:.1f} MB"


def _format_date(ts: float) -> str:
    try:
        return time.strftime("%Y-%m-%d", time.localtime(ts))
    except (ValueError, OSError):
        return "—"


# ── Data Preview ─────────────────────────────────────────────────────────────
def _render_data_preview() -> None:
    info = get_active_info()
    right_html = (
        f'<span style="font-size:11px;color:var(--text-3);font-family:var(--mono);">'
        f'{"Showing first 8 rows" if info else "no active dataset"}</span>'
    )
    with st.container(key="rgf_panel_preview"):
        _panel_open("rgf_panel_preview", "Data Preview", right_html=right_html)
        if not info:
            empty_state("eye_off", "Nothing to preview",
                        "Select a dataset from the list above to preview its first rows.")
        else:
            ensure_registered(info.table_name)
            v = table_version(info.table_name)
            df = head(info.table_name, v, 8)
            _render_preview_table(df)


def _render_preview_table(df: pd.DataFrame) -> None:
    if df.empty:
        empty_state("inbox", "Empty result", "The active table has no rows.")
        return
    cols = ["#"] + list(df.columns)
    ths = "".join(f'<th>{html_mod.escape(str(c))}</th>' for c in cols)
    rows = []
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        tds = [f'<td class="rgf-rd-rownum">{i}</td>']
        for c in df.columns:
            tds.append(f'<td>{_fmt_preview(row[c])}</td>')
        rows.append(f'<tr>{"".join(tds)}</tr>')
    st.markdown(
        '<div class="rgf-preview-wrap"><table class="rgf-preview-table">'
        f'<thead><tr>{ths}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table></div>',
        unsafe_allow_html=True,
    )


def _fmt_preview(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        if v != v:        # NaN
            return ""
        return f"{v:,.4f}" if abs(v) < 1e6 else f"{v:.3g}"
    return html_mod.escape(str(v))
