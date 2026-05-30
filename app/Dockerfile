# ── Stage 1: dependencies ────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS builder

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml .
RUN uv sync --no-dev

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm

WORKDIR /app

# Copy installed packages from builder (keeps image small, no build tools)
COPY --from=builder /app/.venv /app/.venv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY main.py .

# Non-root user — required by Kyverno PSS restricted policy
USER 1000

EXPOSE 8080

# APP_VERSION is passed as build-arg by CI and baked into the image
# This makes the running version visible at /version without querying the registry
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION} \
    APP_COLOR=green \
    APP_ENV=dev \
    FEATURE_FLAG=off \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
