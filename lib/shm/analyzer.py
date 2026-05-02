"""lib/shm/analyzer.py — SHM time-series analytics.

Pure functions over pandas Series / DataFrames — no Streamlit or
DuckDB. Imported by the SHM views; trivial to unit-test in isolation.

Public:
    ``sensor_stats(s)``         — basic per-column summary
    ``rolling_anomalies(s, …)`` — outliers vs rolling mean ± Nσ
    ``daily_aggregates(df, …)`` — resample to daily / hourly / weekly
    ``trend_slope(s)``          — linear-fit slope (units / day)
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sensor_stats(series: pd.Series) -> dict:
    """Compact statistical summary of a single sensor column.

    Returns: ``{n, n_valid, nan_frac, min, max, mean, std, first, last,
    drift, range, peak_dev}``.

    ``drift`` is the (last − first) reading — gives a quick sense of
    long-term displacement / temperature creep / etc. ``peak_dev`` is
    the maximum absolute deviation from the mean: catches transient
    excursions that ``drift`` misses.
    """
    s = series.dropna()
    n_valid = int(s.size)
    n_total = int(series.size)
    if n_valid == 0:
        return {
            "n": n_total, "n_valid": 0, "nan_frac": 1.0,
            "min": np.nan, "max": np.nan, "mean": np.nan, "std": np.nan,
            "first": np.nan, "last": np.nan, "drift": np.nan,
            "range": np.nan, "peak_dev": np.nan,
        }
    return {
        "n": n_total,
        "n_valid": n_valid,
        "nan_frac": 1.0 - n_valid / n_total,
        "min": float(s.min()),
        "max": float(s.max()),
        "mean": float(s.mean()),
        "std": float(s.std()),
        "first": float(s.iloc[0]),
        "last": float(s.iloc[-1]),
        "drift": float(s.iloc[-1] - s.iloc[0]),
        "range": float(s.max() - s.min()),
        "peak_dev": float((s - s.mean()).abs().max()),
    }


def rolling_anomalies(
    series: pd.Series,
    *,
    window: int = 60,
    sigma: float = 3.0,
) -> pd.Series:
    """Boolean mask of points that exceed ``mean ± sigma·std`` of a
    rolling window. Used by the Anomaly view.

    ``window`` is in samples (not minutes). For a 1-min sampling rate,
    ``window=60`` ≈ a 1-hour rolling baseline.

    NaN inputs propagate to NaN in the rolling stats — those positions
    return ``False`` (no anomaly flag) since we can't classify them.
    """
    if window < 5 or sigma <= 0 or series.size == 0:
        return pd.Series(False, index=series.index)
    roll = series.rolling(window=window, min_periods=max(5, window // 4),
                           center=True)
    mu = roll.mean()
    sd = roll.std()
    deviation = (series - mu).abs()
    threshold = sigma * sd
    flagged = (deviation > threshold) & series.notna() & sd.notna()
    return flagged.fillna(False).astype(bool)


# Resample-rule lookup. Streamlit-side picks one of these by id and
# pandas applies the resulting offset alias.
RESAMPLE_RULES: dict[str, str] = {
    "raw":     "",            # no resample
    "5min":    "5min",
    "hourly":  "1h",
    "daily":   "1D",
    "weekly":  "7D",
}


def daily_aggregates(
    df: pd.DataFrame, rule: str = "daily", agg: str = "mean",
) -> pd.DataFrame:
    """Resample the DataFrame's time index to a coarser period.

    ``df.index`` must be a ``DatetimeIndex``. ``rule`` is one of
    ``RESAMPLE_RULES`` (case-insensitive id, NOT a pandas offset
    alias). ``agg`` is one of ``"mean"``, ``"min"``, ``"max"``,
    ``"std"``, ``"first"``, ``"last"`` — applied to every numeric
    column.
    """
    rule_alias = RESAMPLE_RULES.get(rule.lower(), "")
    if not rule_alias:
        return df
    if not isinstance(df.index, pd.DatetimeIndex):
        return df
    valid_aggs = {"mean", "min", "max", "std", "first", "last", "median"}
    if agg not in valid_aggs:
        agg = "mean"
    return df.resample(rule_alias).agg(agg)


def trend_slope(series: pd.Series) -> float:
    """Linear-fit slope in **units per day**.

    Handles a ``DatetimeIndex`` by converting to days-since-first-sample;
    falls back to a sample-index linear fit when the index isn't
    temporal. NaN values are dropped before the fit; returns 0.0 when
    there aren't enough valid points.
    """
    s = series.dropna()
    if s.size < 2:
        return 0.0
    if isinstance(s.index, pd.DatetimeIndex):
        x = (s.index - s.index[0]).total_seconds().to_numpy() / 86400.0
    else:
        x = np.arange(s.size, dtype=float)
    y = s.to_numpy(dtype=float)
    # numpy polyfit deg=1 returns [slope, intercept]
    try:
        slope, _ = np.polyfit(x, y, 1)
        return float(slope)
    except Exception:
        return 0.0
