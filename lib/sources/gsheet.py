"""Google Sheets source — fetch a sheet as CSV via the export endpoint.

Two ingest paths are supported here, both of which only need HTTP
(no Sheets API key, no OAuth, no service account):

1. **Publish-to-web URL** — File → Share → Publish to web → CSV.
   The published link looks like
   ``https://docs.google.com/spreadsheets/d/e/<token>/pub?gid=<gid>&output=csv``
   and is anyone-who-has-the-link readable by design.

2. **Edit / share URL** with sharing set to "Anyone with the link can
   view" — we extract the sheet id (and ``gid`` if present) from the
   URL, then build the standard CSV-export endpoint
   ``https://docs.google.com/spreadsheets/d/<id>/export?format=csv&gid=<gid>``.
   Google permits anonymous CSV export for these sheets.

For PRIVATE sheets you'll need a service-account JSON via Cloud Run
secret (or OAuth) — the upgrade path is to swap ``_fetch_csv`` for a
``gspread`` client. We keep the public-URL path as the default because
it works out of the box on Cloud Run with no IAM setup.

Public:
    ``fetch_to_disk(url, session_id) -> Path`` — download + save CSV
    ``parse_url(url) -> tuple[str, str | None]`` — (sheet_id, gid)
    ``SUPPORTED_HOSTS`` — substrings used to recognise a Sheets URL
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from pathlib import Path

from ..ingest import session_upload_dir


SUPPORTED_HOSTS = ("docs.google.com/spreadsheets",)


# ── URL parsing ─────────────────────────────────────────────────────────────
_SHEET_ID_RE = re.compile(r"/spreadsheets/d/(?:e/)?([A-Za-z0-9_-]+)")
_GID_FRAGMENT_RE = re.compile(r"[?&#]gid=([0-9]+)")


def parse_url(url: str) -> tuple[str, str | None]:
    """Return ``(sheet_id, gid)`` for any Google Sheets URL form.

    Both edit-style links (``/spreadsheets/d/<id>/edit#gid=…``) and
    publish-to-web links (``/spreadsheets/d/e/<token>/pub?gid=…``) are
    handled; the second token captured via the ``e/`` prefix is the
    publish token, which the export endpoint also accepts.

    Raises ``ValueError`` if the URL doesn't look like a Sheets URL.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("Sheet URL is empty")
    u = url.strip()
    if not any(h in u for h in SUPPORTED_HOSTS):
        raise ValueError(
            "Not a Google Sheets URL. Expected a https://docs.google.com/"
            "spreadsheets/... link."
        )
    m = _SHEET_ID_RE.search(u)
    if not m:
        raise ValueError(
            "Couldn't find a sheet id in the URL. Make sure you copied "
            "the full link from the address bar (or the publish-to-web "
            "link from File → Share → Publish to web)."
        )
    sheet_id = m.group(1)
    gid_match = _GID_FRAGMENT_RE.search(u)
    gid = gid_match.group(1) if gid_match else None
    return sheet_id, gid


def _build_export_url(sheet_id: str, gid: str | None, *, published: bool) -> str:
    """Return the canonical CSV-export URL for the sheet.

    ``published=True`` routes through the ``/pub`` endpoint (which the
    sheet owner has explicitly opened with File → Publish to web);
    otherwise we use the standard ``/export?format=csv`` endpoint that
    works for any anyone-with-the-link-viewer sheet.
    """
    qs: dict[str, str] = {"output": "csv"} if published else {"format": "csv"}
    if gid is not None:
        qs["gid"] = gid
    if published:
        base = f"https://docs.google.com/spreadsheets/d/e/{sheet_id}/pub"
    else:
        base = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
    return f"{base}?{urllib.parse.urlencode(qs)}"


# ── Main API — fetch + save ────────────────────────────────────────────────
def fetch_to_disk(url: str, session_id: str, *, filename: str | None = None) -> Path:
    """Download a Google Sheet as CSV and write it under
    ``data/uploads/<session>/<filename>``.

    Returns the on-disk path so callers can pass it straight to
    ``lib.ingest.ingest_file`` — the rest of the pipeline (CSV → Parquet
    → DuckDB view → metadata) is source-agnostic.

    Raises ``ValueError`` if the URL is malformed and ``RuntimeError``
    if the download fails (HTTP error, sharing not open, etc.).
    """
    sheet_id, gid = parse_url(url)
    is_published = "/spreadsheets/d/e/" in url

    # Try published-style first if applicable, else /export. We do a
    # single attempt: a 401 / 403 here means the sheet isn't shared
    # publicly, and we surface a helpful message instead of retrying.
    export_url = _build_export_url(sheet_id, gid, published=is_published)
    try:
        with urllib.request.urlopen(export_url, timeout=30) as resp:  # nosec B310
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise RuntimeError(
                f"Sheet returned {e.code} — the sharing setting must be "
                "either 'Anyone with the link · Viewer' or File → Share → "
                "Publish to web (CSV)."
            ) from e
        if e.code == 404:
            raise RuntimeError(
                "Sheet not found (404). Double-check the URL and whether "
                "the tab still exists."
            ) from e
        raise RuntimeError(f"HTTP {e.code} fetching sheet: {e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Couldn't reach Google Sheets: {e.reason}") from e

    # Defensive: if Google sent us an HTML sign-in page (sharing not
    # open) instead of CSV bytes, refuse and tell the user.
    if "text/html" in content_type.lower() and b"<html" in data[:200].lower():
        raise RuntimeError(
            "Google returned an HTML page instead of CSV — the sheet is "
            "probably private. Set sharing to 'Anyone with the link' or "
            "publish the tab as CSV."
        )

    # Pick a stable filename. Default: sheet-<id>[-gid<gid>].csv so
    # repeat fetches overwrite cleanly.
    if not filename:
        gid_part = f"-gid{gid}" if gid else ""
        filename = f"sheet-{sheet_id[:12]}{gid_part}.csv"
    elif not filename.lower().endswith(".csv"):
        filename = filename + ".csv"

    dest_dir = session_upload_dir(session_id)
    dest = dest_dir / filename
    dest.write_bytes(data)
    return dest
