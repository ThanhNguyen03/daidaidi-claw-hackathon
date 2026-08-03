# =============================================================================
# Backend Dockerfile — built by docker-compose.prod.yml for the team's own VPS
# =============================================================================
# Multi-stage build for production-optimized image
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH=/opt/venv/bin:$PATH
ENV PIP_REQUIRE_HASHES=0

# Install dependencies. Defaults to the full requirements.txt so existing builds
# are unchanged; the server deployment passes REQUIREMENTS=requirements-prod.txt.
ARG REQUIREMENTS=requirements.txt
COPY requirements*.txt ./
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r ${REQUIREMENTS}

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Copy application
COPY . /app
WORKDIR /app

# Change ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Default port; docker-compose.prod.yml overrides this to 8000 via `environment:`
# (host nginx proxies /api/ to backend:8000 — see docker-compose.prod.yml). The
# app reads PORT from the env either way.
ENV PORT=8080
EXPOSE 8080

# Health check (uses python's stdlib so we don't need curl in the slim image).
# Reads $PORT at check time rather than hardcoding 8080, so it still reports
# correctly when docker-compose overrides PORT (production runs on 8000 — a
# hardcoded 8080 here would show the container as permanently "unhealthy" in
# `docker ps` despite the app working fine on the port that's actually mapped).
HEALTHCHECK --interval=180s --timeout=10s --start-period=120s --retries=5 \
    CMD python -c "import os,urllib.request,sys; p=os.environ.get('PORT','8080'); sys.exit(0 if urllib.request.urlopen(f'http://localhost:{p}/health').status==200 else 1)" || exit 1

# Run the application (binds to $PORT).
CMD ["python", "-m", "main"]
