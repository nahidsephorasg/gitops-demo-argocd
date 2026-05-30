"""
GitOps Demo App

Designed to make deployments *visible*:
- /         → returns version, color, hostname (changes with every deploy)
- /health   → liveness/readiness probe
- /version  → just the version string (easy to grep in demo)
- /env      → shows current config (reflects ConfigMap / env changes)
- /break    → starts returning 500s (demo circuit breaker / rollback)
- /metrics  → Prometheus metrics

Environment variables (controlled by Kustomize overlays / GitOps):
  APP_VERSION     = image tag injected by CI (default: dev)
  APP_COLOR       = green | blue (canary / A-B demo)
  APP_ENV         = dev | prod
  FEATURE_FLAG    = on | off  (feature flag demo)
  BREAK_ENABLED   = true      (injected by /break endpoint, reset by redeploy)
"""

import os
import socket
import time
from fastapi import FastAPI, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# ── Config from environment (changed by GitOps without code changes) ──────────
APP_VERSION   = os.getenv("APP_VERSION", "dev")
APP_COLOR     = os.getenv("APP_COLOR", "green")
APP_ENV       = os.getenv("APP_ENV", "dev")
FEATURE_FLAG  = os.getenv("FEATURE_FLAG", "off")
HOSTNAME      = socket.gethostname()   # pod name — proves load balancing across replicas

# Mutable state — reset to False on every new deploy (demonstrates rollback)
_broken = False

# ── Prometheus metrics ─────────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "demo_requests_total",
    "Total requests",
    ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "demo_request_duration_seconds",
    "Request latency",
    ["endpoint"]
)

app = FastAPI(title="GitOps Demo App", version=APP_VERSION)


@app.middleware("http")
async def track_metrics(request, call_next):
    start = time.time()
    response = await call_next(request)
    latency = time.time() - start
    REQUEST_COUNT.labels(request.method, request.url.path, response.status_code).inc()
    REQUEST_LATENCY.labels(request.url.path).observe(latency)
    return response


@app.get("/")
def root():
    """Main endpoint — shows everything that changes with a new deployment."""
    if _broken:
        return Response(
            content='{"error": "broken", "reason": "POST /break was called"}',
            status_code=500,
            media_type="application/json"
        )
    return {
        "app": "gitops-demo",
        "version": APP_VERSION,        # ← changes with every CI push
        "color": APP_COLOR,            # ← changes in canary overlay
        "env": APP_ENV,                # ← dev vs prod overlay
        "feature_flag": FEATURE_FLAG,  # ← feature flag demo
        "hostname": HOSTNAME,          # ← different on each replica (load balancing)
        "status": "healthy",
    }


@app.get("/health")
def health():
    """Kubernetes liveness + readiness probe."""
    if _broken:
        return Response(status_code=503, content='{"status":"broken"}',
                        media_type="application/json")
    return {"status": "ok"}


@app.get("/version")
def version():
    """Just the version — easy to curl and grep in demos."""
    return {"version": APP_VERSION, "color": APP_COLOR}


@app.get("/env")
def env_info():
    """Shows current environment config — reflects ConfigMap / env var changes."""
    return {
        "APP_VERSION":  APP_VERSION,
        "APP_COLOR":    APP_COLOR,
        "APP_ENV":      APP_ENV,
        "FEATURE_FLAG": FEATURE_FLAG,
        "HOSTNAME":     HOSTNAME,
    }


@app.post("/break")
def break_app():
    """
    Injects failures — simulates a bad deployment.
    Demo: deploy → POST /break → see 503s → trigger rollback → 200s return.
    Reset automatically on next deploy (pod restart resets _broken=False).
    """
    global _broken
    _broken = True
    return {"status": "broken", "message": "App is now returning 500s. Rollback to fix."}


@app.post("/fix")
def fix_app():
    """Manually restore health without redeployment (for demo convenience)."""
    global _broken
    _broken = False
    return {"status": "fixed"}


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
