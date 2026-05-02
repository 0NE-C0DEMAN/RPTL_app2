# SHM Dashboard — GCP Deployment Guide

End-to-end instructions for deploying the SHM (Structural Health Monitoring) Streamlit app to Google Cloud Platform. **Cloud Run** is the recommended target. Alternatives (App Engine, GKE, Compute Engine) are sketched at the bottom for context.

---

## TL;DR — one-time setup, then push-to-deploy

```bash
# 0. Pick your project & region
export PROJECT_ID=your-gcp-project-id
export REGION=us-central1
export REPO=shm-dashboard
export SERVICE=shm-dashboard

# 1. Enable the APIs we need
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  --project="$PROJECT_ID"

# 2. Create an Artifact Registry repo for the image
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="SHM Dashboard container images" \
  --project="$PROJECT_ID"

# 3. Build + push the image in one shot (uses Cloud Build remotely)
gcloud builds submit --tag \
  "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$SERVICE:latest" \
  --project="$PROJECT_ID"

# 4. Deploy to Cloud Run
gcloud run deploy "$SERVICE" \
  --image="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$SERVICE:latest" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --memory=2Gi --cpu=2 \
  --timeout=900 \
  --session-affinity \
  --concurrency=80 \
  --min-instances=0 --max-instances=10 \
  --project="$PROJECT_ID"
```

The URL comes back in the last line of output (`https://shm-dashboard-xxxx.a.run.app`). That's it.

For push-to-deploy via Cloud Build, skip step 3 and wire `cloudbuild.yaml` to a trigger (see *Continuous deployment* below).

---

## Why Cloud Run (vs other options)

| Target | Fit for Streamlit | Notes |
|---|---|---|
| **Cloud Run** ✅ | Great | Managed container runtime, WebSockets supported (since 2021), scale-to-zero, generous free tier, HTTPS + custom domains built-in. Matches Streamlit's one-process-per-request model. |
| App Engine Standard | Poor | No WebSockets on standard. Streamlit won't work. |
| App Engine Flexible | OK but clunky | Works, but slow deploys, minimum 1 instance 24/7 (cost), deprecated-ish. |
| GKE | Overkill | Only consider if you already run a GKE cluster or need stateful sessions / sticky upload storage across replicas. |
| Compute Engine VM | Possible | Cheap, full control, but you manage OS updates, SSL, scaling, uptime. Good for a pinned demo; bad for a product. |

**Use Cloud Run** unless you have a specific reason not to.

---

## Pre-flight: what the container needs

Everything below is already in the repo:

| File | Purpose |
|---|---|
| `Dockerfile` | Builds a Python 3.11 slim image, installs `requirements.txt`, launches `streamlit run` bound to `0.0.0.0:$PORT`. Sets `enableCORS=false` + `enableXsrfProtection=false` for proxy-friendliness. |
| `.dockerignore` | Keeps the image <~400 MB by excluding `.git`, notebooks, PNG references, the RPLT zip, etc. |
| `requirements.txt` | Pinned Python deps. Already trimmed to what `lib/` + `views/` import. |
| `runtime.txt` | `python-3.11` — informational / App Engine compatibility. |
| `cloudbuild.yaml` | Three-step CI/CD: build → push → deploy. Wired to Cloud Build triggers. |
| `.streamlit/config.toml` | Theme + `maxUploadSize=2000` (MB). CORS/XSRF overridden by the Dockerfile CLI flags when running in a container. |

---

## Step-by-step: first-time deploy

### 1. Install `gcloud` and authenticate

```bash
# Install Google Cloud SDK (macOS / Linux / Windows — see cloud.google.com/sdk)
gcloud auth login
gcloud config set project your-gcp-project-id
gcloud auth configure-docker us-central1-docker.pkg.dev
```

### 2. Enable required APIs

```bash
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com
```

### 3. Create an Artifact Registry repo

Artifact Registry is the modern replacement for Container Registry. Don't use `gcr.io` — it's sunset.

```bash
gcloud artifacts repositories create shm-dashboard \
  --repository-format=docker \
  --location=us-central1 \
  --description="SHM Dashboard container images"
```

### 4. Build the image

#### Option A — remote build with Cloud Build (no local Docker needed)

```bash
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/$PROJECT_ID/shm-dashboard/shm-dashboard:latest
```

This ships your source tree to Cloud Build, runs the Dockerfile server-side, and pushes the result to Artifact Registry. Takes ~3–5 min for the first build, ~1 min thereafter.

#### Option B — local build, then push

```bash
docker build -t us-central1-docker.pkg.dev/$PROJECT_ID/shm-dashboard/shm-dashboard:latest .
docker push    us-central1-docker.pkg.dev/$PROJECT_ID/shm-dashboard/shm-dashboard:latest
```

Faster iteration if you've already built the image locally.

### 5. Deploy to Cloud Run

```bash
gcloud run deploy shm-dashboard \
  --image=us-central1-docker.pkg.dev/$PROJECT_ID/shm-dashboard/shm-dashboard:latest \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --memory=2Gi --cpu=2 \
  --timeout=900 \
  --session-affinity \
  --concurrency=80 \
  --min-instances=0 --max-instances=10
```

**What each flag does:**

- `--allow-unauthenticated` — public URL. Drop this and use IAP/OAuth if the app is internal (see *Locking it down* below).
- `--memory=2Gi` — Streamlit + DuckDB + pandas processing a 2 GB upload needs headroom. 2 GB handles files up to ~500 MB comfortably; bump to 4 GB for larger.
- `--cpu=2` — 2 vCPUs. Cloud Run charges per CPU-second even idle, so don't over-provision.
- `--timeout=900` — 15 minutes. Streamlit opens a WebSocket that lives as long as the browser tab, so the connection-timeout must be high. Max is 3600 (1 h).
- `--session-affinity` — **critical**. Routes one user's requests to the same instance so their uploaded file (stored in the instance's ephemeral `/app/data/`) stays reachable during their session.
- `--concurrency=80` — up to 80 simultaneous browser tabs per instance.
- `--min-instances=0` — scales to zero between uses (no cost when idle). Set to `1` for always-warm (~$0.05/hour).
- `--max-instances=10` — cap to protect the wallet in case of a traffic spike.

---

## Continuous deployment via Cloud Build

Every push to `main` can auto-build and ship a new revision. One-time setup:

### 1. Grant Cloud Build the right IAM roles

```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
CB_SA=$PROJECT_NUMBER@cloudbuild.gserviceaccount.com

# Deploy to Cloud Run
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:$CB_SA --role=roles/run.admin

# Cloud Run services run as the Compute Engine default service account,
# which Cloud Build has to "act as" to deploy.
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:$CB_SA --role=roles/iam.serviceAccountUser

# Push to Artifact Registry
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:$CB_SA --role=roles/artifactregistry.writer
```

### 2. Connect the GitHub repo

Cloud Console → Cloud Build → Triggers → **Connect Repository** → authorise GitHub → select `0NE-C0DEMAN/RPLT_Dashboard`.

### 3. Create the trigger

Cloud Console → Cloud Build → Triggers → **Create Trigger**:

- Event: *Push to a branch*
- Branch: `^main$`
- Configuration: *Cloud Build configuration file (yaml or json)*
- Location: `cloudbuild.yaml`
- Substitutions (override if needed):
  - `_REGION`: `us-central1`
  - `_REPO`: `shm-dashboard`
  - `_SERVICE`: `shm-dashboard`

Now every push to `main` auto-builds, pushes, and deploys a new Cloud Run revision tagged with the commit SHA.

### Rolling back

Each revision is pinned to a specific image SHA in Artifact Registry:

```bash
gcloud run revisions list --service=shm-dashboard --region=us-central1
gcloud run services update-traffic shm-dashboard \
  --region=us-central1 \
  --to-revisions=shm-dashboard-00034-abc=100
```

---

## Production hardening (optional)

### Lock down access (auth'd only)

Drop `--allow-unauthenticated` and add IAP or member-based access:

```bash
# Remove public access
gcloud run services remove-iam-policy-binding shm-dashboard \
  --region=us-central1 --member=allUsers --role=roles/run.invoker

# Grant access to specific users / groups
gcloud run services add-iam-policy-binding shm-dashboard \
  --region=us-central1 \
  --member=user:alice@example.com --role=roles/run.invoker
# or a group
#   --member=group:engineering@example.com --role=roles/run.invoker
```

Users will need to authenticate with their Google account on first visit.

### Custom domain

```bash
gcloud run domain-mappings create \
  --service=shm-dashboard \
  --domain=rplt.yourcompany.com \
  --region=us-central1
```

Cloud Run generates the DNS records you need to add to your registrar and provisions a TLS certificate automatically.

### Persistent storage for uploads

By default every Cloud Run instance has its own ephemeral filesystem — per-user uploads vanish when the instance recycles. For production, back `data/` with Cloud Storage:

1. Create a bucket: `gsutil mb -l us-central1 gs://shm-dashboard-data`
2. Mount it with Cloud Storage FUSE — add to `Dockerfile`:
   ```dockerfile
   RUN apt-get update && apt-get install -y gcsfuse
   ```
   And to the startup command:
   ```bash
   gcsfuse --implicit-dirs shm-dashboard-data /app/data && streamlit run ...
   ```
3. Or refactor `lib/ingest.py` to write to GCS via `google-cloud-storage` directly (cleaner, no FUSE dependency).

For a demo / review app, ephemeral storage is fine — users upload, explore, leave. Next session starts clean.

### Secrets / credentials

Use **Secret Manager** for any credentials (Google Sheets OAuth, Slack webhooks, etc.):

```bash
# Create secret
echo -n "mysecretvalue" | gcloud secrets create google-service-account \
  --data-file=- --replication-policy=automatic

# Grant Cloud Run runtime access
gcloud secrets add-iam-policy-binding google-service-account \
  --member=serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor

# Mount at deploy time
gcloud run deploy shm-dashboard --update-secrets=GSA_JSON=google-service-account:latest ...
```

The app reads the value as `os.environ["GSA_JSON"]`. Don't bake secrets into the image.

### Monitoring

Cloud Run ships logs to Cloud Logging automatically (view in the console under **Cloud Run → shm-dashboard → Logs**). For structured logging, use `structlog` or `logging` with a JSON formatter. For metrics + alerts, Cloud Monitoring pulls revision / request / CPU metrics from Cloud Run out-of-the-box.

---

## Cost estimate

Cloud Run pricing (us-central1):

- **Compute**: $0.024 per vCPU-hour (only charged when handling a request, or always if `--min-instances≥1`)
- **Memory**: $0.0025 per GiB-hour
- **Requests**: $0.40 per million requests
- **Free tier**: 180k vCPU-seconds + 360k GiB-seconds + 2M requests / month

Demo workload (engineer uses it 1h/day, 20 days/month, 2 vCPU + 2 GiB):

```
2 vCPU × 20 × 1h × $0.024  = $0.96/month compute
2 GiB  × 20 × 1h × $0.0025 = $0.10/month memory
≈ 50 requests/day                    ≈ $0.00 (in free tier)
                            TOTAL: ~$1/month
```

Almost free on the free tier for a single-engineer review tool.

---

## Local verification (optional but recommended)

Before pushing to Cloud Build, sanity-check the Dockerfile locally:

```bash
# Build
docker build -t shm-dashboard .

# Run (Cloud Run's default port)
docker run --rm -p 8080:8080 -e PORT=8080 shm-dashboard

# Visit http://localhost:8080
```

Watch for:

- ✅ Starts in <10 s
- ✅ LOAD DEMO button works (file at `RPLTResults (1).xlsx` is in the image)
- ✅ Dashboard renders the KPIs correctly
- ✅ Settings page loads
- ✅ No WebSocket / XSRF errors in the browser console

---

## Alternatives (brief)

### App Engine Flexible

```bash
# app.yaml (already compatible)
runtime: custom
env: flex
resources:
  cpu: 2
  memory_gb: 2

gcloud app deploy
```

Works, but slow deploys (5–10 min), always-on billing (no scale-to-zero), and feels increasingly like a legacy platform. **Prefer Cloud Run.**

### GKE

Only consider if you already run a GKE cluster. Wrap the Dockerfile in a standard Deployment + Service + Ingress. Use `sessionAffinity: ClientIP` on the Service for sticky uploads.

### Compute Engine VM

```bash
gcloud compute instances create-with-container shm-dashboard \
  --machine-type=e2-medium \
  --container-image=us-central1-docker.pkg.dev/$PROJECT_ID/shm-dashboard/shm-dashboard:latest \
  --tags=http-server,https-server

# + firewall rule for :8080, or put an HTTPS load balancer in front
```

Cheap for a pinned demo URL, but you manage everything.

---

## Troubleshooting

**Container exits immediately with `Port X is already in use`.** Something is using the `PORT` env var in a way Streamlit doesn't like. Ensure the Dockerfile's CMD uses `--server.port=${PORT}` (shell form) — array-form CMD won't expand `$PORT`.

**`WebSocket connection failed`.** `enableXsrfProtection` / `enableCORS` not disabled. Confirm the Dockerfile's CMD passes `--server.enableCORS=false --server.enableXsrfProtection=false`.

**Cloud Run deploy fails with `permission denied for service account`.** The Cloud Build SA needs `roles/iam.serviceAccountUser` on the Cloud Run runtime SA (default `$PROJECT_NUMBER-compute@developer.gserviceaccount.com`). See *Continuous deployment* above.

**Upload times out or fails mid-file.** Cloud Run request bodies are capped at 32 MB by default. Increase: add `--max-request-size=2048Mi` to the deploy command (if your gcloud supports it), or chunk the upload client-side.

**App cold-starts slowly (10–20 s on first request).** Set `--min-instances=1` so one warm instance is always available (~$15/month). Don't do this in dev — scale-to-zero is free.

**User's upload disappears mid-session.** Cloud Run may route their next request to a different instance. Add `--session-affinity` (already in the Quick Start). For bulletproof persistence, move `data/` to GCS.
