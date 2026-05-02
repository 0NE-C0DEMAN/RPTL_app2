"""lib/shm — Structural Health Monitoring domain logic.

Long-term sensor monitoring data (LVDTs, tiltmeters, thermocouples) has
a different shape from RPLT impact tests: continuous time series
spanning days / weeks, multiple sensors of multiple types, regular
sampling, gaps from sensor dropouts. The RPLT-side helpers (cycle
detection, event windowing, derive-from-load) don't apply.

Public:
    ``classify_columns(cols)``      — group columns by sensor type
    ``sensor_stats(df, col)``       — min/max/mean/std/drift/NaN-frac
    ``rolling_anomalies(...)``      — outliers from rolling mean ± Nσ
    ``daily_aggregates(df, agg)``   — resample to daily summaries
"""
from __future__ import annotations

from .columns import (
    SENSOR_PALETTES, SENSOR_TYPES, classify_columns,
    color_for_sensor, sensor_color, sensor_label, sensor_unit,
)
from .analyzer import (
    RESAMPLE_RULES, daily_aggregates, rolling_anomalies,
    sensor_stats, trend_slope,
)
from .loader import get_active_dataset, load_dataset, resampled_view

__all__ = [
    "SENSOR_PALETTES", "SENSOR_TYPES", "classify_columns",
    "color_for_sensor", "sensor_color", "sensor_label", "sensor_unit",
    "RESAMPLE_RULES", "daily_aggregates", "rolling_anomalies",
    "sensor_stats", "trend_slope",
    "get_active_dataset", "load_dataset", "resampled_view",
]
