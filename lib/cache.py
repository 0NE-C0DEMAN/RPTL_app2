"""Cache + table-registration helpers.

Two responsibilities:

1. ``table_version(table)`` returns a float that changes whenever the
   underlying parquet file changes. Pass it as an arg to ``@st.cache_data``
   functions to invalidate them automatically when the data changes.

2. ``ensure_registered(table)`` re-registers a parquet file as a DuckDB
   view if the view has been lost (e.g. after a server restart). Call
   it at the top of every view that touches data.

Both paths are hot on tab switches — ``ensure_all_imported_registered``
runs from ``app.py`` on every rerun and ``table_version`` / ``ensure_registered``
are called by every view's render. We memoise at the process level
(``@lru_cache``) so reruns short-circuit when the underlying state
hasn't changed.
"""

from __future__ import annotations

from pathlib import Path

from .ingest import load_metadata
from .db import list_tables, register_parquet


def table_version(table: str) -> float:
    """Return the parquet file's mtime — changes when data changes."""
    info = load_metadata(table)
    if not info:
        return 0.0
    p = Path(info.parquet_path)
    return p.stat().st_mtime if p.exists() else 0.0


def ensure_registered(table: str) -> bool:
    """Re-register a table's parquet view if missing. Returns True on success.

    First check is the cached ``_registered`` set; DuckDB's ``list_tables``
    is only consulted on a miss, which is the expensive path."""
    if table in _registered:
        return True
    if table in list_tables():
        _registered.add(table)
        return True
    info = load_metadata(table)
    if not info:
        return False
    p = Path(info.parquet_path)
    if not p.exists():
        return False
    register_parquet(table, info.parquet_path)
    _registered.add(table)
    return True


# Process-level registry of tables we've confirmed live in DuckDB this run.
# Survives Streamlit reruns (script re-execution doesn't reload modules),
# so after the first registration per session subsequent reruns are O(1).
_registered: set[str] = set()


def ensure_all_imported_registered(tables: list[str]) -> None:
    """Re-register every table that should be live in this session.

    After the first pass per session, this becomes a no-op — the cached
    set short-circuits before we ever hit DuckDB or the filesystem."""
    if not tables:
        return
    # Fast path: all already registered
    if all(t in _registered for t in tables):
        return
    for t in tables:
        ensure_registered(t)
