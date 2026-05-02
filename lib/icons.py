"""
lib/icons.py — SVG icon path data (ported from components/icons.jsx).

Usage:
    from lib.icons import svg
    st.markdown(svg("dashboard", size=18), unsafe_allow_html=True)

All icons are stroke-only (fill="none", stroke="currentColor") so they pick up
the parent CSS color — the same path renders in any context (sidebar dark,
button muted, accent-tinted hover).
"""
from __future__ import annotations

ICONS: dict[str, str] = {
    "dashboard":  "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 22V12h6v10",
    "upload":     "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M17 8l-5-5-5 5 M12 3v12",
    "chart":      "M18 20V10 M12 20V4 M6 20v-6",
    "wave":       "M2 12c1.5-3 3-6 5-6s3.5 6 5 6 3.5-6 5-6 3.5 3 5 6",
    "cycle":      "M21 12a9 9 0 1 1-6.219-8.56 M21 3v6h-6",
    "report":     "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8",
    "table":      "M12 3v18 M3 9h18 M3 15h18 M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5z",
    "settings":   ("M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"),
    "download":   "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M7 10l5 5 5-5 M12 15V3",
    "chev_down":  "M6 9l6 6 6-6",
    "chev_right": "M9 18l6-6-6-6",
    "check":      "M20 6L9 17l-5-5",
    "x":          "M18 6L6 18 M6 6l12 12",
    "plus":       "M12 5v14 M5 12h14",
    "zap":        "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
    "layers":     "M12 2L2 7l10 5 10-5-10-5z M2 17l10 5 10-5 M2 12l10 5 10-5",
    "search":     "M11 17.25a6.25 6.25 0 1 1 0-12.5 6.25 6.25 0 0 1 0 12.5z M16 16l4.5 4.5",
    "filter":     "M22 3H2l8 9.46V19l4 2v-8.54L22 3z",
    "printer":    "M6 9V2h12v7 M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2 M6 14h12v8H6z",
    "eye":        "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    "clock":      "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 7v5l3 3",
    "info":       "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 16v-4 M12 8h.01",
    "arrow_up":   "M12 19V5 M5 12l7-7 7 7",
    "arrow_down": "M12 5v14 M19 12l-7 7-7-7",
    "menu":       "M3 12h18 M3 6h18 M3 18h18",
    "grip":       "M9 4h.01 M15 4h.01 M9 9h.01 M15 9h.01 M9 14h.01 M15 14h.01 M9 19h.01 M15 19h.01",
    # ── Empty-state iconography (replaces the emoji set) ────────────────
    "alert":      "M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z M12 9v4 M12 17h.01",
    "inbox":      "M22 12h-6l-2 3h-4l-2-3H2 M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z",
    "database":   "M12 8c4.97 0 9-1.57 9-3.5S16.97 1 12 1 3 2.57 3 4.5 7.03 8 12 8z M3 5v6c0 1.93 4.03 3.5 9 3.5s9-1.57 9-3.5V5 M3 12v6c0 1.93 4.03 3.5 9 3.5s9-1.57 9-3.5v-6",
    "sliders":    "M4 21v-7 M4 10V3 M12 21v-9 M12 8V3 M20 21v-5 M20 12V3 M1 14h6 M9 8h6 M17 16h6",
    "ruler":      "M3 21l3-3 M21 3l-6 6 M21 3L9 15 M3 21L15 9 M6 12l-3 3 M12 18l-3 3 M18 6l3-3 M18 12l3-3",
    "eye_off":    "M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94 M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19 M14.12 14.12a3 3 0 1 1-4.24-4.24 M1 1l22 22",
    "folder":     "M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z",
    "save":       "M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z M17 21v-8H7v8 M7 3v5h8",
    "plug":       "M18.36 5.64a9 9 0 1 1-12.73 0 M12 2v10",
}


def svg(name: str, size: int = 18, color: str = "currentColor", stroke_width: float = 1.8) -> str:
    """Return an inline SVG element for icon ``name``.

    ``color="currentColor"`` makes the stroke pick up the parent CSS color —
    useful inside nav items, buttons, badges.
    """
    d = ICONS.get(name, "")
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="{d}"/>'
        f'</svg>'
    )
