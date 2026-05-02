"""Reusable DuckDB query templates with Streamlit caching.

Thin wrappers around DuckDB that every view composes on top of. The
heavy lifting lives in ``lib.processing`` and ``lib.charts.canvas``.

CACHING: every function takes a ``version: float`` argument (the
parquet file's mtime, see ``cache.table_version``). When the file
changes, the version changes and the cache is invalidated automatically.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from .db import get_connection, get_columns, quote_table_identifier


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    dtype: str
    is_numeric: bool
    is_temporal: bool


# ---------------------------------------------------------------------------
# Schema introspection (cached)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, max_entries=64)
def get_schema(table: str, version: float = 0.0) -> list[ColumnInfo]:
    cols = get_columns(table)
    out = []
    for name, dtype in cols:
        d = dtype.upper()
        is_numeric = any(t in d for t in (
            "INT", "DECIMAL", "DOUBLE", "FLOAT", "REAL", "NUMERIC"
        ))
        is_temporal = any(t in d for t in ("TIMESTAMP", "DATE", "TIME"))
        out.append(ColumnInfo(name, dtype, is_numeric, is_temporal))
    return out


@st.cache_data(show_spinner=False, max_entries=64)
def column_names(table: str, version: float = 0.0) -> list[str]:
    return [c.name for c in get_schema(table, version)]


# ---------------------------------------------------------------------------
# Custom SQL + raw fetches (cached)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, max_entries=128)
def run_custom_query(sql: str, version: float = 0.0) -> pd.DataFrame:
    """Execute arbitrary SQL — cached by SQL string + version."""
    con = get_connection()
    return con.execute(sql).fetchdf()


@st.cache_data(show_spinner=False, max_entries=32)
def head(table: str, version: float = 0.0, n: int = 100) -> pd.DataFrame:
    con = get_connection()
    qt = quote_table_identifier(table)
    return con.execute(f"SELECT * FROM {qt} LIMIT {int(n)}").fetchdf()
