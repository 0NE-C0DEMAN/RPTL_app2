# SHM Dashboard

A Streamlit app for **Structural Health Monitoring** (SHM) data — long-term sensor recordings (LVDTs, tiltmeters, thermocouples, strain gauges, vibrating wires, pressure transducers) over days, weeks, or months. Built for engineers who need to look at multi-channel time series, find anomalies, track drift, and spot data-quality problems at a glance.

![SHM Dashboard](https://img.shields.io/badge/Streamlit-≥1.40-FF4B4B) ![Python](https://img.shields.io/badge/Python-3.11-3776AB) ![License](https://img.shields.io/badge/license-internal-lightgrey)

---

## What it does

Drop a CSV / Parquet / XLSX of timestamped sensor readings (or paste a Google Sheets link, or click *Load Demo*) and the app gives you, without any further configuration:

| View | What you see |
|------|--------------|
| **Overview** | Dataset KPI strip (time span, sample rate, sensor count, coverage) + per-sensor-family time-series overlay paired with a diagnostics rail (max-drift hero + per-channel min/max/drift) |
| **Sensor Browser** | Health KPIs (most-drifted, most-volatile, lowest-coverage channel) + per-sensor chart + 7-cell stat strip (min · max · μ · σ · drift · slope · coverage) |
| **Time Series** | Multi-sensor overlay with resample (raw / 5min / hourly / daily / weekly) + aggregation (mean / min / max / std / median); auto-routes mixed-unit sensors to dual axes |
| **Correlation** | Pearson r heatmap with diverging palette + colour-scale legend; scatter inspector with time-quartile-tinted cloud, regression line, mean reference lines, and r/r²/slope readout |
| **Anomaly Detection** | Rolling-σ outlier flagging per sensor with adjustable window + threshold; KPI strip of total anomalies, rate, and worst excursion; right-rail list of first flagged timestamps |
| **Trend / Drift** | Per-family daily-mean overlay with linear-fit lines + slope rail showing every channel's slope and drift |
| **Data Quality** | Per-sensor coverage Gantt: green = covered, red = gap; KPI strip of avg coverage, longest gap, total outage episodes; worst-offender list |
| **Raw Data** | Searchable, paginated table of the underlying dataset with CSV export |

A **global time-window filter** sits at the top of every data view (Last 24h / 7d / 30d / All / Custom), anchored to the dataset's own latest sample, so every chart and KPI re-scopes with one click.

## Sensor recognition

Columns are auto-classified by name into sensor families. The classifier is regex-based and case-insensitive — drop a CSV with columns like `LVDT1`, `Tilt4`, `Thermocouple_2`, `Strain_A`, `VWP1`, `PT_3` and the app groups, colours, and unit-labels them automatically:

| Family | Patterns | Default unit | Palette |
|--------|----------|--------------|---------|
| LVDT (Displacement) | `lvdt`, `displ` | mm | blues |
| Tiltmeter | `tilt`, `inclin` | ° | ambers |
| Thermocouple | `therm`, `temp` | °C | reds |
| Strain Gauge | `strain`, `gauge` | µε | violets |
| Vibrating Wire | `vw`, `vib` | Hz | cyans |
| Pressure | `press`, `bar` | kPa | limes |
| Other | (fallback) | — | slates |

Each individual sensor within a family gets a distinct shade so five LVDTs on the same chart are still visually distinguishable, with a clickable legend chip per series for show / hide.

## Tech stack

- **Streamlit** ≥ 1.40 (one-page UI with `@st.fragment` scoping)
- **DuckDB** for ingest (CSV / XLSX → Parquet → SQL view, never loads the full file into Python memory)
- **PyArrow + pandas** for analytics
- **NumPy + SciPy** for rolling-σ, linear fits, percentiles
- **LTTB** for peak-preserving downsampling (keeps anomalies visible on 45k-row recordings)
- **Vanilla JS + HTML5 Canvas** chart engine (single iframe per chart via `st.components.v1.html`)
- **Custom JS click-dispatch bridge** (HTML data-attrs → hidden `st.button`s, no full reload)

## Quick start

### Local

```bash
git clone https://github.com/0NE-C0DEMAN/RPTL_app2.git
cd RPTL_app2
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py --server.port 8502
```

The app boots on `http://localhost:8502`. Click **Load Demo** in the Import view to ingest the bundled `demo/all_sensors_demo.csv` (March 2020, 11 channels, 45k rows).

### Docker

```bash
docker build -t shm-dashboard .
docker run -p 8080:8080 -e PORT=8080 shm-dashboard
```

### Cloud Run (push to deploy)

A full Cloud Build pipeline is provided in `cloudbuild.yaml` — wire it to a Cloud Build trigger on this repo and every commit to `main` ships a fresh revision to Cloud Run with `--allow-unauthenticated`, `--session-affinity` (so a user's WebSocket stays pinned to one instance), and `--max-instances=10`. See [`DEPLOYMENT.md`](./DEPLOYMENT.md) for one-time IAM setup.

## Data sources

Three source adapters live under `lib/sources/`. Each returns a Path on disk; the rest of the pipeline is source-agnostic.

- **Manual upload** — `st.file_uploader` accepting `.csv` / `.tsv` / `.txt` / `.xlsx` / `.xls` / `.parquet` (up to 2 GB, streamed to disk in 8 MB chunks)
- **Google Sheets URL** — paste any sheet whose sharing is *Anyone with the link · Viewer* or that has been *Published to web (CSV)*; no auth, no service account, no IAM setup. Private sheets are an upgrade to `gspread` away (swap `_fetch_csv` in `lib/sources/gsheet.py`).
- **Bundled demo** — `demo/all_sensors_demo.csv` ships in the repo; auto-loads via the *Load Demo* button.

## CSV schema

The first column is treated as the timestamp; everything else is numeric sensor data. Empty header cells are auto-renamed (`Unnamed: 0` → `timestamp`), whitespace-only cells are coerced to NaN, and rows with malformed timestamps are dropped at load time.

```csv
timestamp,LVDT1,LVDT2,Tilt4,Thermocouple1
2020-03-01 00:00:00,5.2522,4.4627,-4.5365,22.7320
2020-03-01 00:01:00,5.2581,4.4584,-4.5604,22.7199
...
```

## Project layout

```
.
├── app.py                  # Streamlit entry point + view dispatcher
├── lib/
│   ├── shell.py            # Sidebar HTML, NAV table, footer
│   ├── bridge.py           # JS click-dispatch (visible HTML → hidden st.button)
│   ├── theme.py            # CSS template loader
│   ├── tokens.py           # Design tokens (colours, radii, typography)
│   ├── components.py       # page_header, kpi_strip, section_heading, print_panel, …
│   ├── timewindow.py       # Global time-window filter + preset bar
│   ├── ingest.py           # CSV/XLSX → Parquet pipeline (DuckDB COPY)
│   ├── db.py               # DuckDB connection + table registration
│   ├── queries.py          # Cached SELECT helpers
│   ├── cache.py            # Re-register parquet views on rerun
│   ├── state.py            # Session state + on-load hydration from data/cache
│   ├── icons.py            # Inline SVG library
│   ├── charts/             # Canvas chart engine (1043-line iframe template)
│   ├── shm/                # Domain logic
│   │   ├── columns.py      # Sensor-type classifier + per-channel palettes
│   │   ├── analyzer.py     # Stats, rolling anomalies, daily aggregates, slope
│   │   └── loader.py       # Cached time-indexed DataFrame loader
│   └── sources/
│       ├── manual.py       # st.file_uploader → Path
│       └── gsheet.py       # Google Sheets URL → CSV → Path
├── views/                  # One module per top-level view
├── assets/rgf.css          # Single CSS template, format_map'd with tokens at boot
├── demo/all_sensors_demo.csv
├── Dockerfile
├── cloudbuild.yaml
├── DEPLOYMENT.md
├── requirements.txt
└── runtime.txt             # python-3.11 (pinned for Cloud Run)
```

## Performance notes

- **Ingest**: a 1 GB CSV becomes a ~150 MB Parquet via `COPY ... TO 'file.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)` without ever loading the whole file into Python memory.
- **Loader**: `lib/shm/loader.load_dataset(table, version, time_col)` is cached on (table, mtime) so tab switches cost zero — every view that touches data calls this single function.
- **Downsampling**: chart panels run **LTTB** (Largest Triangle Three Buckets) on the joint envelope of all visible series, capped at 1500–2000 points per chart. Peak-preserving — anomalies and spikes don't disappear between strides.
- **Cache invalidation**: every cached function takes the parquet's mtime as a key, so re-ingesting a file busts the cache automatically.

## Roadmap (not yet built)

- Event annotations (engineer-marked events: load test, calibration, retrofit) shown as vertical lines on every chart
- Threshold rules / alerts ("warn if LVDT exceeds 5.5 mm or σ exceeds 2× baseline")
- Comparison-with-baseline view (last 7 days vs first 7 days)
- PDF / PNG report export

## License

Internal project. Not for external distribution.
