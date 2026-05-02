# ──────────────────────────────────────────────────────────────────────────
# SHM Dashboard — production container
#
# Targets Google Cloud Run (primary) but also runs on any container host
# that injects $PORT (Render, Fly, Railway, local `docker run`).
#
# Build:   docker build -t rplt-dashboard .
# Run:     docker run -p 8080:8080 -e PORT=8080 rplt-dashboard
# Cloud Run auto-injects PORT=8080 and handles TLS termination.
# ──────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

# Keep stdout/err unbuffered so Cloud Logging captures prints immediately.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    # Streamlit telemetry / analytics off — demo app, no tracking
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    # Cloud Run default port; app.py / CMD honour whatever $PORT is set to.
    PORT=8080

WORKDIR /app

# ── System deps ──────────────────────────────────────────────────────────
# Only what we need for DuckDB / PyArrow / pandas wheels. No build-tools
# since everything ships as wheels for py3.11-slim.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── Python deps (cached layer) ───────────────────────────────────────────
# Copy ONLY requirements.txt first so dep installs are cached across
# source-code changes. Rebuilds only happen when requirements change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── App source ───────────────────────────────────────────────────────────
COPY . .

# ── Writable working directories ─────────────────────────────────────────
# ingest.py writes to data/uploads, data/parquet, data/cache. Cloud Run's
# filesystem is writable but ephemeral per-instance — that's fine for a
# demo / review dashboard. For a stateful production deploy, mount a
# Cloud Storage FUSE volume or swap lib/ingest.py to write to GCS.
RUN mkdir -p data/uploads data/parquet data/cache

# Cloud Run exposes whatever port the container listens on — let the
# platform know we're on $PORT (informational).
EXPOSE 8080

# ── Start command ────────────────────────────────────────────────────────
# Shell form so $PORT expands at runtime. Flags below are critical for
# running behind Cloud Run's HTTPS load balancer:
#   --server.address=0.0.0.0      — bind to all interfaces
#   --server.port=$PORT           — listen on whatever Cloud Run gave us
#   --server.headless=true        — skip the "open browser" prompt
#   --server.enableCORS=false     — LB terminates origin; CORS check
#                                   fails otherwise
#   --server.enableXsrfProtection=false
#                                 — same reason; Streamlit's XSRF check
#                                   is origin-based and breaks behind LBs
#   --browser.gatherUsageStats=false
CMD streamlit run app.py \
    --server.address=0.0.0.0 \
    --server.port=${PORT} \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false
