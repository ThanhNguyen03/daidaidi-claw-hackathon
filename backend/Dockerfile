# =============================================================================
# Backend Dockerfile for AgentBase Runtime Deployment
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

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Copy application
COPY . /app
WORKDIR /app

# Change ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# AgentBase Runtime Service Contract: the platform routes traffic to port 8080
# and probes GET /health. The app reads PORT from the env, so pin it to 8080.
# (Locally you can override with -e PORT=8000.)
ENV PORT=8080
EXPOSE 8080

# Health check (uses python's stdlib so we don't need curl in the slim image)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/health').status==200 else 1)" || exit 1

# Run the application (binds to $PORT = 8080). GREENNODE_* creds are auto-injected
# by AgentBase Runtime — do NOT bake them into the image.
CMD ["python", "-m", "main"]