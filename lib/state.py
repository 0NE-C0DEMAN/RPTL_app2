"""Streamlit session state helpers.

Tracks the currently-active table, the user's session id, and the
list of imported tables in this session.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

import streamlit as st

from .ingest import CACHE_DIR, TableInfo, load_metadata
from .db import drop_table


_KEY_SESSION_ID = "rgf_session_id"
_KEY_ACTIVE_TABLE = "rgf_active_table"
_KEY_IMPORTED = "rgf_imported_tables"
_KEY_HYDRATED = "rgf_state_hydrated"


def session_id() -> str:
    if _KEY_SESSION_ID not in st.session_state:
        st.session_state[_KEY_SESSION_ID] = uuid.uuid4().hex[:12]
    return st.session_state[_KEY_SESSION_ID]


def hydrate_from_disk() -> None:
    """Rebuild ``imported_tables`` + ``active_table`` from on-disk metadata.

    Streamlit session state is per-WebSocket — a fresh tab / hard reload
    loses whatever ``set_active_table()`` and ``add_imported()`` did in
    the previous session. But the ingested parquet files + their
    ``data/cache/<table>.json`` metadata persist on disk.

    This scans those JSON files once per session and restores:
      * ``imported_tables`` — list of every still-on-disk table name
      * ``active_table``    — the most recently ingested one (so the
                              Overview / Sensor views render data instead
                              of an empty-state on every reload)

    Idempotent within a session via ``_KEY_HYDRATED``. Won't undo a
    user-initiated "Clear All" mid-session: once hydrated, this is a
    no-op.
    """
    if st.session_state.get(_KEY_HYDRATED):
        return
    st.session_state[_KEY_HYDRATED] = True
    if not CACHE_DIR.exists():
        return
    entries: list[tuple[float, str]] = []
    for p in CACHE_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text())
            tname = data.get("table_name") or p.stem
            ingested_at = float(data.get("ingested_at", 0.0))
            parquet_path = data.get("parquet_path", "")
            # Skip orphan metadata whose parquet vanished.
            if parquet_path and not Path(parquet_path).exists():
                continue
            entries.append((ingested_at, tname))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    if not entries:
        return
    entries.sort(reverse=True)  # most recent first
    seen: set[str] = set()
    ordered: list[str] = []
    for _, tname in entries:
        if tname not in seen:
            seen.add(tname)
            ordered.append(tname)
    st.session_state[_KEY_IMPORTED] = ordered
    if not st.session_state.get(_KEY_ACTIVE_TABLE):
        st.session_state[_KEY_ACTIVE_TABLE] = ordered[0]


def set_active_table(table_name: str) -> None:
    st.session_state[_KEY_ACTIVE_TABLE] = table_name


def get_active_table() -> Optional[str]:
    return st.session_state.get(_KEY_ACTIVE_TABLE)


def get_active_info() -> Optional[TableInfo]:
    name = get_active_table()
    if not name:
        return None
    return load_metadata(name)


def imported_tables() -> list[str]:
    if _KEY_IMPORTED not in st.session_state:
        st.session_state[_KEY_IMPORTED] = []
    return st.session_state[_KEY_IMPORTED]


def add_imported(table_name: str) -> None:
    items = imported_tables()
    if table_name not in items:
        items.append(table_name)
        st.session_state[_KEY_IMPORTED] = items


def remove_imported(table_name: str) -> None:
    items = imported_tables()
    if table_name in items:
        items.remove(table_name)
        st.session_state[_KEY_IMPORTED] = items
        drop_table(table_name)
        # Invalidate the cache.py registry so subsequent
        # ``ensure_registered`` re-checks DuckDB for this table.
        from .cache import _registered
        _registered.discard(table_name)
        if get_active_table() == table_name:
            st.session_state[_KEY_ACTIVE_TABLE] = None
