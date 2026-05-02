"""DuckDB connection management.

Single in-memory DuckDB instance shared across the Streamlit session.
Files are registered as views over their on-disk Parquet representation,
so DuckDB streams from disk and never holds the full dataset in memory.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import streamlit as st


@st.cache_resource(show_spinner=False)
def get_connection() -> duckdb.DuckDBPyConnection:
    """Return the singleton DuckDB connection for this Streamlit process.

    Cached at resource level so it survives Streamlit reruns. Configured
    to stream Parquet from disk with bounded memory.
    """
    con = duckdb.connect(database=":memory:")
    con.execute("SET memory_limit = '4GB'")
    con.execute("SET threads = 4")
    con.execute("SET preserve_insertion_order = false")
    return con


def register_parquet(table_name: str, parquet_path: str | Path) -> None:
    """Register a Parquet file as a DuckDB view. Idempotent."""
    con = get_connection()
    safe_name = _safe_name(table_name)
    path_str = str(Path(parquet_path).resolve()).replace("'", "''")
    con.execute(f"DROP VIEW IF EXISTS {safe_name}")
    con.execute(
        f"CREATE VIEW {safe_name} AS SELECT * FROM read_parquet('{path_str}')"
    )


def drop_table(table_name: str) -> None:
    con = get_connection()
    safe_name = _safe_name(table_name)
    con.execute(f"DROP VIEW IF EXISTS {safe_name}")


def list_tables() -> list[str]:
    con = get_connection()
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_type = 'VIEW' "
        "ORDER BY table_name"
    ).fetchall()
    return [r[0] for r in rows]


def get_columns(table_name: str) -> list[tuple[str, str]]:
    """Return (column_name, dtype) pairs."""
    con = get_connection()
    safe_name = _safe_name(table_name)
    rows = con.execute(f"DESCRIBE {safe_name}").fetchall()
    return [(r[0], r[1]) for r in rows]


def get_row_count(table_name: str) -> int:
    con = get_connection()
    safe_name = _safe_name(table_name)
    return con.execute(f"SELECT COUNT(*) FROM {safe_name}").fetchone()[0]


def _safe_name(name: str) -> str:
    """Quote an identifier for safe SQL interpolation."""
    cleaned = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
    if cleaned and cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return f'"{cleaned}"'


def quote_table_identifier(name: str) -> str:
    """Public quoter for dynamic table names in SQL."""
    return _safe_name(name)


def quote_identifier(name: str) -> str:
    """Public quoter for column names in dynamic SQL."""
    escaped = name.replace('"', '""')
    return f'"{escaped}"'
