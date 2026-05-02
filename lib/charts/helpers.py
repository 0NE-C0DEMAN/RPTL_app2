"""Shared chart helpers — cycle landmarks + aggregation primitives."""

from __future__ import annotations

import numpy as np


def find_unloading_point(load: np.ndarray, velocity: np.ndarray) -> int | None:
    """Index where velocity crosses zero after peak load (the UPM anchor)."""
    if len(load) < 3 or len(velocity) < 3:
        return None
    peak_idx = int(np.argmax(np.abs(load)))
    if peak_idx >= len(velocity) - 1:
        return None
    tail = velocity[peak_idx:]
    signs = np.sign(tail)
    crossings = np.where(np.diff(signs) != 0)[0]
    if len(crossings) == 0:
        return peak_idx + int(np.argmin(np.abs(tail)))
    return peak_idx + int(crossings[0])


def detect_event_window(
    load: np.ndarray,
    threshold_pct: float = 0.05,
    buffer_pct: float = 0.15,
    min_buffer: int = 10,
    *,
    contiguous_run: int = 0,
) -> tuple[int, int]:
    """Return (start, end) indices of the RPLT load event.

    Default behaviour walks from the FIRST / LAST above-threshold sample
    — fine for single-event records where the signal returns to 0 after
    the impact.

    For long acquisitions with a rising baseline (e.g. an acquisition
    log whose Load summ ends at a non-zero DC level), pass
    ``contiguous_run > 0``. The window then sits around the peak and is
    bounded by the first run of ``contiguous_run`` consecutive below-
    threshold samples on either side. This isolates the actual impact
    impulse and discards everything else.
    """
    n = len(load)
    if n == 0:
        return 0, 0
    abs_load = np.abs(load)
    peak = float(np.max(abs_load))
    if peak <= 0:
        return 0, n
    threshold = peak * threshold_pct
    mask = abs_load > threshold
    if mask.sum() < 5:
        return 0, n

    if contiguous_run > 0:
        # Contiguous-run mode — anchored at peak, widen outward until
        # ``contiguous_run`` below-threshold samples are seen in a row.
        peak_idx = int(np.argmax(abs_load))
        # Walk forward
        end = n - 1
        below = 0
        for i in range(peak_idx, n):
            if not mask[i]:
                below += 1
                if below >= contiguous_run:
                    end = i - contiguous_run + 1
                    break
            else:
                below = 0
        # Walk backward
        start = 0
        below = 0
        for i in range(peak_idx, -1, -1):
            if not mask[i]:
                below += 1
                if below >= contiguous_run:
                    start = i + contiguous_run - 1
                    break
            else:
                below = 0
        # Add the usual buffer so the plot doesn't start / end at the
        # threshold-crossing point (ugly).
        buf = max(min_buffer, int((end - start) * buffer_pct))
        return max(0, start - buf), min(n, end + buf)

    first = int(np.argmax(mask))
    last = n - 1 - int(np.argmax(mask[::-1]))
    buf = max(min_buffer, int((last - first) * buffer_pct))
    return max(0, first - buf), min(n, last + buf)


# ── Chart-Builder aggregation primitives ─────────────────────────────────────
def histogram_bins(
    data: np.ndarray, bins: int = 40,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute a histogram — return (bin_centers, counts).

    Bin centers are plotted as the X axis and counts as the Y values in
    a bar chart. NaN values are dropped before binning.
    """
    arr = np.asarray(data, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 2:
        return np.array([]), np.array([])
    counts, edges = np.histogram(arr, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2.0
    return centers, counts.astype(float)


def box_summary(data: np.ndarray) -> dict:
    """Return the 5-number summary for a box plot.

    Keys: min, q1, median, q3, max. Returns ``None`` for each when the
    array has no valid values.
    """
    arr = np.asarray(data, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 1:
        return {"min": None, "q1": None, "median": None, "q3": None, "max": None}
    return {
        "min":    float(np.min(arr)),
        "q1":     float(np.percentile(arr, 25)),
        "median": float(np.median(arr)),
        "q3":     float(np.percentile(arr, 75)),
        "max":    float(np.max(arr)),
    }
