"""lib/shm/columns.py — sensor-column classification.

Looks at column NAMES (the only metadata we have at ingest time) and
buckets each column into a sensor type. Types drive:

* Default chart palette (LVDTs blue, tiltmeters amber, thermocouples red).
* Default unit for axis labels.
* Grouping in the Sensors browser view.
* Choice of left vs right axis when overlaid on the Composite chart.

The classifier is regex-based and case-insensitive. New sensor types
can be added by appending to ``SENSOR_TYPES`` — the rest of the app
picks them up via ``classify_columns()``.
"""
from __future__ import annotations

import re


# (id, label, unit, color, list-of-name-patterns)
#
# Pattern note: "LVDT1" is a single word in regex terms, so a trailing
# ``\b`` between "T" and "1" doesn't match (both are word chars). Use
# bare prefixes — ``\blvdt`` matches "LVDT1", "lvdt_2", "Lvdtmm" all
# the same. Patterns are tested case-insensitively.
SENSOR_TYPES: list[dict] = [
    {
        "id":       "lvdt",
        "label":    "LVDT (Displacement)",
        "unit":     "mm",
        "color":    "#3b82f6",   # blue
        "patterns": [r"\blvdt", r"\bdispl"],
    },
    {
        "id":       "tilt",
        "label":    "Tiltmeter",
        "unit":     "°",
        "color":    "#f59e0b",   # amber
        "patterns": [r"\btilt", r"\binclin"],
    },
    {
        "id":       "thermo",
        "label":    "Thermocouple",
        "unit":     "°C",
        "color":    "#ef4444",   # red
        "patterns": [r"\btherm", r"\btemp"],
    },
    {
        "id":       "strain",
        "label":    "Strain Gauge",
        "unit":     "µε",
        "color":    "#8b5cf6",   # violet
        "patterns": [r"\bstrain", r"\bgauge"],
    },
    {
        "id":       "vw",
        "label":    "Vibrating Wire",
        "unit":     "Hz",
        "color":    "#06b6d4",   # cyan
        "patterns": [r"\bvw", r"\bvib"],
    },
    {
        "id":       "press",
        "label":    "Pressure",
        "unit":     "kPa",
        "color":    "#84cc16",   # lime
        "patterns": [r"\bpress", r"\bbar"],
    },
    {
        "id":       "other",
        "label":    "Other",
        "unit":     "",
        "color":    "#94a3b8",   # slate
        "patterns": [],
    },
]


def _type_of(col_name: str) -> str:
    """Return the ``id`` of the matching sensor type for a column name.

    First-match wins, so order in ``SENSOR_TYPES`` matters. Falls
    through to ``"other"`` when no pattern matches.
    """
    low = col_name.lower()
    for t in SENSOR_TYPES:
        for pat in t["patterns"]:
            if re.search(pat, low):
                return t["id"]
    return "other"


def classify_columns(cols: list[str]) -> dict[str, list[str]]:
    """Group columns by sensor-type id.

    Returns ``{type_id: [col_name, …]}`` for every type that has at
    least one matching column. Keeps original column ordering within
    each group.
    """
    out: dict[str, list[str]] = {}
    for c in cols:
        out.setdefault(_type_of(c), []).append(c)
    return out


def sensor_label(col_name: str) -> str:
    """Human-readable sensor-type label for a column (e.g. ``"LVDT (Displacement)"``)."""
    tid = _type_of(col_name)
    for t in SENSOR_TYPES:
        if t["id"] == tid:
            return t["label"]
    return "Other"


def sensor_unit(col_name: str) -> str:
    """Default unit string for a column based on its type."""
    tid = _type_of(col_name)
    for t in SENSOR_TYPES:
        if t["id"] == tid:
            return t["unit"]
    return ""


def sensor_color(col_name: str) -> str:
    """Default chart colour for a column based on its type."""
    tid = _type_of(col_name)
    for t in SENSOR_TYPES:
        if t["id"] == tid:
            return t["color"]
    return "#94a3b8"


# Per-sensor distinct shades within each type family. When five LVDTs
# overlay on one chart, each gets a different blue so the legend is
# actually readable. Order = visual distinguishability (alternating
# light / mid / dark so adjacent sensors don't blur together).
SENSOR_PALETTES: dict[str, list[str]] = {
    "lvdt":   ["#60a5fa", "#1d4ed8", "#7dd3fc", "#0ea5e9", "#3b82f6",
               "#1e40af", "#38bdf8", "#2563eb"],
    "tilt":   ["#fbbf24", "#d97706", "#fde68a", "#f59e0b",
               "#b45309", "#fcd34d"],
    "thermo": ["#fca5a5", "#b91c1c", "#fecaca", "#ef4444",
               "#7f1d1d", "#f87171"],
    "strain": ["#c4b5fd", "#6d28d9", "#ddd6fe", "#8b5cf6",
               "#4c1d95", "#a78bfa"],
    "vw":     ["#67e8f9", "#0e7490", "#a5f3fc", "#06b6d4",
               "#155e75", "#22d3ee"],
    "press":  ["#bef264", "#4d7c0f", "#d9f99d", "#84cc16",
               "#365314", "#a3e635"],
    "other":  ["#cbd5e1", "#64748b", "#e2e8f0", "#94a3b8",
               "#475569", "#94a3b8"],
}


def color_for_sensor(col_name: str, all_cols: list[str]) -> str:
    """Distinct chart colour for a sensor, unique within its type group.

    ``all_cols`` is the complete list of columns being plotted (or the
    full dataset's columns) — we look up where ``col_name`` sits among
    its same-type peers and index into the type's palette.

    Falls back to the type's flagship colour when the type has no
    multi-shade palette defined.
    """
    tid = _type_of(col_name)
    same = [c for c in all_cols if _type_of(c) == tid]
    palette = SENSOR_PALETTES.get(tid)
    if not palette:
        return sensor_color(col_name)
    try:
        idx = same.index(col_name) % len(palette)
    except ValueError:
        return palette[0]
    return palette[idx]
