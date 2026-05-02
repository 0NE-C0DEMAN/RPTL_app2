"""Data source adapters. Each source ends in a Path on disk; everything
downstream is source-agnostic from there.

Available sources:
    ``manual``  — direct file upload via Streamlit ``st.file_uploader``
    ``gsheet``  — fetch a public-link Google Sheet as CSV (no auth)
"""

from . import gsheet, manual

__all__ = ["gsheet", "manual"]
