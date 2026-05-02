"""
lib/tokens.py — Design tokens (single source of truth).

Light theme — CareFi-inspired (soft slate page + white cards + deep
navy text + emerald SHM accent). Built to drop straight into the
existing ``assets/rgf.css`` template, every name here must appear
verbatim as ``{NAME}`` in the CSS file.

History:
    The original SHM theme was dark-mode-first (#1d2737 page,
    #0a0f18 cards). Switched to light per design direction; only
    the surface / text / grid families changed — the emerald accent
    family (the brand colour) is preserved end-to-end.
"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Surfaces ─────────────────────────────────────────────────────────────────
# Page = soft slate; cards = pure white; subtle bg for hover / inner
# pills; "row alt" for striped tables; "header" surfaces (NAVY in dark
# theme) become near-white with a faint grey separator.
BG             = "#F4F6FB"   # page background (soft slate)
SURFACE        = "#FFFFFF"   # card / panel background
BG_SOFT        = "#EFF2F8"   # subtle inner surfaces (pills, hover targets)
BG_ROW_ALT     = "#F8FAFC"   # table striping
BORDER         = "#E3E7EF"   # default border
BORDER_SOFT    = "#ECEFF5"   # row separators / softer dividers
NAVY           = "#FFFFFF"   # sidebar / header bar (now white)
NAVY_LIGHT     = "#EFF2F8"   # subtle gradient stop (was darker navy)
TEXT           = "#0E1733"   # primary text — deep navy (CareFi)
TEXT_2         = "#5A6478"   # secondary text — muted slate
TEXT_3         = "#8A93A6"   # tertiary / micro labels
NAV_TEXT       = "#5A6478"   # sidebar nav idle
NAV_ICON       = "#8A93A6"   # sidebar nav icon idle
NAV_MUTED      = "#8A93A6"   # sidebar subtitles
GRID           = "#ECEFF5"   # plot grid lines (very faint)

# ── Accent (emerald — SHM brand colour) ──────────────────────────────────────
# Re-tuned for legibility on light surfaces: text-on-light shifts to a
# darker green (#047857) instead of the previous near-white hint.
ACCENT         = "#10B981"   # brand primary
ACCENT_DARK    = "#059669"   # primary button hover / active
ACCENT_LIGHT   = "#DCFCE7"   # tint bg (pale green wash)
ACCENT_SOFT    = "#34D399"   # progress bar lighter stop
ACCENT_DEEP    = "#047857"   # text on tint bg (was #a7f3d0)
ACCENT_BORDER  = "#86EFAC"   # tag border on light surface
ACCENT_TINT    = "#F0FDF4"   # very pale green hover bg

# ── Neutrals ─────────────────────────────────────────────────────────────────
SLATE          = "#5A6478"
SLATE_MUTED    = "#8A93A6"
HOVER_SOFT     = "#EFF2F8"   # button hover bg
UPLOAD_BG      = "#F8FAFC"   # file uploader default bg
WHITE          = "#FFFFFF"

# ── Status colours (deltas, alerts, badges) ─────────────────────────────────
# Each pair is (bg, text) for a subtle pill on a white card.
DELTA_UP_BG     = "#DCFCE7"
DELTA_UP_TEXT   = "#15803D"
DELTA_DOWN_BG   = "#FEE2E2"
DELTA_DOWN_TEXT = "#B91C1C"
WARN_BG         = "#FEF3C7"
WARN_BORDER     = "#FCD34D"
WARN_TEXT       = "#B45309"
WARN_ICON       = "#D97706"

# ── Cloud-provider accents (unchanged hex; legible on white) ────────────────
GOOGLE_GREEN   = "#34A853"
GOOGLE_BLUE    = "#4285F4"

# ── Radii ────────────────────────────────────────────────────────────────────
RADIUS_SM = 6
RADIUS_MD = 10
RADIUS_LG = 14

# ── Sidebar dimensions ───────────────────────────────────────────────────────
SIDEBAR_W           = 240
SIDEBAR_W_COLLAPSED = 64


def tokens_dict() -> dict[str, str | int]:
    """Flat dict for CSS template interpolation via ``str.format_map``.

    Every name here must appear verbatim as ``{NAME}`` in
    ``assets/rgf.css``.
    """
    return {
        "BG":             BG,
        "SURFACE":        SURFACE,
        "BG_SOFT":        BG_SOFT,
        "BG_ROW_ALT":     BG_ROW_ALT,
        "BORDER":         BORDER,
        "BORDER_SOFT":    BORDER_SOFT,
        "NAVY":           NAVY,
        "NAVY_LIGHT":     NAVY_LIGHT,
        "TEXT":           TEXT,
        "TEXT_2":         TEXT_2,
        "TEXT_3":         TEXT_3,
        "NAV_TEXT":       NAV_TEXT,
        "NAV_ICON":       NAV_ICON,
        "NAV_MUTED":      NAV_MUTED,
        "GRID":           GRID,
        "ACCENT":         ACCENT,
        "ACCENT_DARK":    ACCENT_DARK,
        "ACCENT_LIGHT":   ACCENT_LIGHT,
        "ACCENT_SOFT":    ACCENT_SOFT,
        "ACCENT_DEEP":    ACCENT_DEEP,
        "ACCENT_BORDER":  ACCENT_BORDER,
        "ACCENT_TINT":    ACCENT_TINT,
        "SLATE":          SLATE,
        "SLATE_MUTED":    SLATE_MUTED,
        "HOVER_SOFT":     HOVER_SOFT,
        "UPLOAD_BG":      UPLOAD_BG,
        "WHITE":          WHITE,
        "DELTA_UP_BG":    DELTA_UP_BG,
        "DELTA_UP_TEXT":  DELTA_UP_TEXT,
        "DELTA_DOWN_BG":  DELTA_DOWN_BG,
        "DELTA_DOWN_TEXT": DELTA_DOWN_TEXT,
        "WARN_BG":        WARN_BG,
        "WARN_BORDER":    WARN_BORDER,
        "WARN_TEXT":      WARN_TEXT,
        "WARN_ICON":      WARN_ICON,
        "GOOGLE_GREEN":   GOOGLE_GREEN,
        "GOOGLE_BLUE":    GOOGLE_BLUE,
        "RADIUS_SM":      RADIUS_SM,
        "RADIUS_MD":      RADIUS_MD,
        "RADIUS_LG":      RADIUS_LG,
        "SIDEBAR_W":      SIDEBAR_W,
        "SIDEBAR_W_COLLAPSED": SIDEBAR_W_COLLAPSED,
    }
