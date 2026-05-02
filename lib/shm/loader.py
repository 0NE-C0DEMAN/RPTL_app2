"""lib/shm/loader.py — cached SHM dataset loader.

Pulls the active table out of DuckDB into a pandas DataFrame indexed
by the timestamp column. Every SHM view (Overview / Sensors / Time
Series / Correlation / Anomaly / Trend / Raw Data) ends up calling
this — so it's cached on (table_name, version) to avoid the SQL +
pandas-conversion cost on every rerun.

The loader optionally resamples (1min / 5min / hourly / daily) and
returns a copy with the time column moved to the index. Sensor
columns stay numeric, NaN-preserving.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from lib.cache import ensure_registered, table_version
from lib.queries import column_names, run_custom_query
from lib.db import quote_table_identifier
from lib.shm.analyzer import RESAMPLE_RULES, daily_aggregates


@st.cache_data(show_spinner=False)
def load_dataset(
    table_name: str, version: float, time_col: str,
) -> pd.DataFrame:
    """Return the full dataset as a time-indexed DataFrame.

    Cached by (table, version) — survives reruns. Time column is
    parsed via pandas (handles ISO strings, common formats); if
    parsing fails we leave it as a numeric column and let the caller
    deal with the consequences.
    """
    qt = quote_table_identifier(table_name)
    df = run_custom_query(f"SELECT * FROM {qt}", version=version)
    if df.empty:
        return df

    # Move time col to the index (parse to datetime if possible).
    if time_col in df.columns:
        ts = pd.to_datetime(df[time_col], errors="coerce")
        if ts.notna().any():
            df = df.set_index(ts).drop(columns=[time_col])
            df.index.name = "timestamp"
            # Drop rows whose timestamp is NaT — these come from
            # malformed source rows. Keeping them breaks any view
            # that strftime-formats df.index[0]/[-1] and triggers
            # ValueError on the chart_panel rerender path.
            df = df[df.index.notna()]
            df = df.sort_index()
        else:
            # Can't parse as datetime — try numeric, then leave as-is.
            num = pd.to_numeric(df[time_col], errors="coerce")
            if num.notna().any():
                df = df.set_index(num).drop(columns=[time_col])
            df.index.name = time_col

    # Coerce sensor columns to numeric. Defensive even though the
    # ingest pass already does this — older parquets cached in
    # ``data/parquet/`` may still hold stringly-typed columns.
    for c in df.columns:
        if df[c].dtype == object or str(df[c].dtype).startswith("string"):
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def resampled_view(
    df: pd.DataFrame, *, rule: str = "raw", agg: str = "mean",
) -> pd.DataFrame:
    """Apply the user's resample rule. ``rule`` is an id from
    ``RESAMPLE_RULES`` (``raw`` / ``5min`` / ``hourly`` / ``daily`` /
    ``weekly``); ``agg`` is one of ``mean`` / ``min`` / ``max`` / ``std``."""
    if rule not in RESAMPLE_RULES or rule == "raw":
        return df
    return daily_aggregates(df, rule=rule, agg=agg)


def get_active_dataset(*, time_col: str | None = None) -> pd.DataFrame | None:
    """Convenience wrapper: load whatever's the active table.

    Reads ``rgf_map_time`` from session state when ``time_col`` isn't
    explicitly passed. Returns ``None`` if no dataset is active.
    """
    from lib.state import get_active_info
    info = get_active_info()
    if info is None:
        return None
    ensure_registered(info.table_name)
    v = table_version(info.table_name)
    if time_col is None:
        time_col = st.session_state.get("rgf_map_time")
        if not time_col:
            cols = column_names(info.table_name, v) or []
            time_col = cols[0] if cols else ""
    return load_dataset(info.table_name, v, time_col)
