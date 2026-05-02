"""File ingestion pipeline.

For every file (CSV / XLSX / Parquet), we:
  1. Save raw file to data/uploads/<session>/<filename>
  2. Convert to Parquet at data/parquet/<session>/<basename>.parquet
  3. Register the Parquet file as a DuckDB view
  4. Return a metadata record describing the table

DuckDB does the conversion via COPY ... TO 'file.parquet' so we never load
the full dataset into Python memory. A 1GB CSV becomes ~150-300MB Parquet.
"""

from __future__ import annotations

import functools
import json
import re
import shutil
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from .db import get_connection, register_parquet, get_columns, get_row_count


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
PARQUET_DIR = DATA_DIR / "parquet"
CACHE_DIR = DATA_DIR / "cache"


def session_upload_dir(session_id: str) -> Path:
    p = UPLOADS_DIR / _safe_dir(session_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def session_parquet_dir(session_id: str) -> Path:
    p = PARQUET_DIR / _safe_dir(session_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------
@dataclass
class TableInfo:
    table_name: str
    source_filename: str
    parquet_path: str
    row_count: int
    column_count: int
    columns: list[tuple[str, str]]
    sheet_name: str | None
    ingested_at: float


def save_metadata(info: TableInfo) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{info.table_name}.json"
    path.write_text(json.dumps(asdict(info), indent=2))


def load_metadata(table_name: str) -> TableInfo | None:
    """Read a table's metadata JSON.

    Results are memoised per-file by the cached ``_read_metadata`` helper —
    the file's mtime is part of the cache key, so edits (re-ingest) bust
    the cache automatically. This cuts the disk-read cost of tab
    switching where the sidebar footer + active view each call
    ``get_active_info()``.
    """
    path = CACHE_DIR / f"{table_name}.json"
    if not path.exists():
        return None
    return _read_metadata(str(path), path.stat().st_mtime)


@functools.lru_cache(maxsize=32)
def _read_metadata(path_str: str, _mtime: float) -> "TableInfo":
    """Cached disk read — key is (path, mtime). Module-level @lru_cache so
    the cache persists across Streamlit reruns (script re-execution does
    NOT re-import the module — function objects stay alive)."""
    data = json.loads(Path(path_str).read_text())
    data["columns"] = [tuple(c) for c in data["columns"]]
    return TableInfo(**data)


# ---------------------------------------------------------------------------
# Saving an uploaded file
# ---------------------------------------------------------------------------
def stream_uploaded_to_disk(uploaded_file, session_id: str) -> Path:
    """Save a Streamlit UploadedFile to disk in fixed-size chunks.

    Streamlit's UploadedFile is a BytesIO buffer — we copy it out so we
    don't keep it in memory longer than necessary.
    """
    dest_dir = session_upload_dir(session_id)
    dest = dest_dir / uploaded_file.name
    with open(dest, "wb") as fh:
        # Write in 8MB chunks
        while True:
            chunk = uploaded_file.read(8 * 1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
    uploaded_file.seek(0)
    return dest


def copy_local_to_session(src: Path, session_id: str) -> Path:
    """Used by the demo data button — copy a local file into the session dir."""
    src = Path(src)
    if not src.is_file():
        raise FileNotFoundError(f"Demo source not found: {src}")
    dest_dir = session_upload_dir(session_id)
    dest = dest_dir / src.name
    if not dest.exists() or dest.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dest)
    return dest


DEMO_BUNDLED_CSV = PROJECT_ROOT / "demo" / "all_sensors_demo.csv"


def resolve_demo_ingest_path(session_id: str) -> Path:
    """Path to the demo SHM dataset for ingestion.

    Prefer the bundled ``demo/all_sensors_demo.csv`` (March 2020 data,
    11 sensors × ~45k rows). If missing on the runtime filesystem,
    synthesize a smaller mock so Load Demo still works.
    """
    if DEMO_BUNDLED_CSV.exists():
        try:
            return copy_local_to_session(DEMO_BUNDLED_CSV, session_id)
        except OSError:
            pass
    dest = session_upload_dir(session_id) / "all_sensors_demo.csv"
    if not dest.exists():
        _write_synthetic_demo_csv(dest)
    return dest


def _write_synthetic_demo_csv(dest: Path) -> None:
    """Tiny SHM-flavoured CSV — 1 LVDT, 1 tilt, 1 thermocouple over a
    week at 1-min sampling. Used as a fallback when the bundled demo
    file isn't available at runtime."""
    import numpy as np
    import pandas as pd

    n = 7 * 24 * 60         # 1 week, 1-min sampling
    t = pd.date_range("2024-01-01", periods=n, freq="1min")
    rng = np.random.default_rng(42)
    # Diurnal temperature swing + slow drift
    temp = 22.0 + 6.0 * np.sin(2 * np.pi * np.arange(n) / (24 * 60)) + rng.normal(0, 0.3, n)
    # Displacement that roughly tracks temperature (thermal expansion)
    disp = 5.0 + 0.05 * (temp - 22.0) + rng.normal(0, 0.01, n)
    # Slow tilt drift
    tilt = -0.5 + np.linspace(0, 0.05, n) + rng.normal(0, 0.005, n)

    df = pd.DataFrame(
        {"timestamp": t, "LVDT1": disp, "Tilt1": tilt, "Thermocouple1": temp}
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(dest, index=False)


# ---------------------------------------------------------------------------
# CSV / XLSX / Parquet → Parquet conversion
# ---------------------------------------------------------------------------
def convert_to_parquet(src: Path, session_id: str,
                       sheet_name: str | None = None) -> tuple[Path, str | None]:
    """Convert any supported file to Parquet. Returns (parquet_path, sheet_used).

    Format detection is by file extension. CSV uses DuckDB's read_csv_auto
    (handles header detection, type inference). XLSX is read via pandas
    (DuckDB's spatial extension can also read xlsx but pandas is simpler).
    Parquet files are simply registered as-is.
    """
    src = Path(src)
    dest_dir = session_parquet_dir(session_id)
    base = src.stem
    if sheet_name:
        base = f"{base}__{_safe_dir(sheet_name)}"
    dest = dest_dir / f"{base}.parquet"

    suffix = src.suffix.lower()
    con = get_connection()
    src_str = str(src.resolve()).replace("'", "''")
    dest_str = str(dest.resolve()).replace("'", "''")

    if suffix == ".parquet":
        # Just register the file in place
        return src, None

    elif suffix in (".csv", ".tsv", ".txt"):
        # Read with pandas (auto-handles header detection + unnamed
        # first columns) and write with DuckDB to Parquet.
        #
        # CSV quirks we have to deal with:
        # 1. Empty header cell in the first column — pandas calls it
        #    "Unnamed: 0"; we rename to "timestamp" via _normalise_col.
        # 2. Whitespace-only entries (" ") sprinkled through numeric
        #    columns — common in SHM acquisition exports. Pandas reads
        #    those as strings, downgrades the WHOLE column to dtype=str,
        #    parquet stores strings, charts can't plot them. We strip
        #    whitespace + treat blank/whitespace-only cells as NA, then
        #    coerce every non-first column to numeric.
        # 3. Source rows with malformed timestamps — left as NaT, picked
        #    up by the loader and dropped via ``df.index.notna()``.
        import pandas as pd
        df = pd.read_csv(
            src,
            skipinitialspace=True,
            na_values=["", " ", "NA", "N/A", "null", "NULL", "nan", "NaN", "—"],
        )
        df.columns = [_normalise_col(c, i) for i, c in enumerate(df.columns)]
        # Force every non-timestamp column to numeric. The first column
        # is left alone — the loader parses it as datetime (or numeric).
        for c in df.columns[1:]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        con.execute(
            f"COPY (SELECT * FROM df) TO '{dest_str}' "
            f"(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        return dest, None

    elif suffix in (".xlsx", ".xls"):
        # Read with pandas, write with DuckDB
        import pandas as pd
        if sheet_name is None:
            xl = pd.ExcelFile(src)
            sheet_name = xl.sheet_names[0]
        df = pd.read_excel(src, sheet_name=sheet_name)
        df.columns = [str(c) for c in df.columns]
        con.execute(
            f"COPY (SELECT * FROM df) TO '{dest_str}' "
            f"(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        return dest, sheet_name

    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def list_excel_sheets(path: Path) -> list[str]:
    import pandas as pd
    return pd.ExcelFile(path).sheet_names


# ---------------------------------------------------------------------------
# Full ingestion pipeline
# ---------------------------------------------------------------------------
def ingest_file(src_path: Path, session_id: str,
                sheet_name: str | None = None,
                table_name: str | None = None) -> TableInfo:
    """End-to-end: convert → register → save metadata → return TableInfo."""
    src_path = Path(src_path)
    parquet_path, sheet_used = convert_to_parquet(src_path, session_id, sheet_name)

    if table_name is None:
        table_name = _table_name_from(src_path, sheet_used)

    register_parquet(table_name, parquet_path)

    cols = get_columns(table_name)
    rows = get_row_count(table_name)

    info = TableInfo(
        table_name=table_name,
        source_filename=src_path.name,
        parquet_path=str(parquet_path),
        row_count=rows,
        column_count=len(cols),
        columns=cols,
        sheet_name=sheet_used,
        ingested_at=time.time(),
    )
    save_metadata(info)
    return info


def _table_name_from(src_path: Path, sheet: str | None) -> str:
    stem = src_path.stem
    if sheet:
        stem = f"{stem}_{sheet}"
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", stem)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")  # collapse multiple _
    if not cleaned:
        cleaned = "table"
    if cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return cleaned.lower()


def _safe_dir(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name)


def _normalise_col(name, idx: int) -> str:
    """Force a usable column name for ingest.

    pandas turns empty header cells into ``Unnamed: 0`` / ``Unnamed: 1``;
    we rename the *first* such column to ``timestamp`` (since SHM CSVs
    usually leave the timestamp column unnamed) and any others to
    ``col_<idx>``. Trailing whitespace + Excel-export ``.1`` suffixes
    on duplicate names get cleaned up too.
    """
    s = str(name).strip()
    if not s or s.lower().startswith("unnamed:"):
        return "timestamp" if idx == 0 else f"col_{idx}"
    return s
