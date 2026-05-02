"""Chart library — Canvas-based panels only.

Every view uses ``lib.charts.canvas.chart_panel`` for its charts. Plotly
and ECharts have been removed from the codebase; the public API is:

    from lib.charts.canvas import chart_panel, series, small_btn, icon_btn
"""

from .canvas import chart_panel, icon_btn, series, small_btn
from .helpers import detect_event_window, find_unloading_point

__all__ = [
    "chart_panel", "icon_btn", "series", "small_btn",
    "detect_event_window", "find_unloading_point",
]
