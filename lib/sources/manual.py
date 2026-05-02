"""Manual file upload source — direct from a Streamlit st.file_uploader."""

from __future__ import annotations

from pathlib import Path

from ..ingest import stream_uploaded_to_disk


# Tab-separated acquisition dumps land as .txt — DuckDB's read_csv_auto
# sniffs the delimiter, so they route through the same CSV path.
SUPPORTED_EXTENSIONS = ["csv", "tsv", "txt", "xlsx", "xls", "parquet"]


def save(uploaded_file, session_id: str) -> Path:
    """Stream the uploaded file to disk and return its path."""
    return stream_uploaded_to_disk(uploaded_file, session_id)
