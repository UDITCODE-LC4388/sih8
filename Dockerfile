# ==============================================================================
# ISRO LUNAR HAZARD-MAP & SAFE LANDING GROUND CONTROL STATION (GCS)
# Production Container Image (Hardened, Zero-Root, Minimal Attack Surface)
# ==============================================================================

FROM python:3.11-slim-bookworm AS runtime

# System Environment Hardening
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    GCS_ENV=production

# Install minimal OS runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user & group
RUN groupadd -r gcsgroup && useradd -r -g gcsgroup -d /app -s /sbin/nologin gcsuser

WORKDIR /app

# Install Python requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy codebase and processed lunar mission assets
COPY --chown=gcsuser:gcsgroup pyproject.toml ./
COPY --chown=gcsuser:gcsgroup src/ ./src/
COPY --chown=gcsuser:gcsgroup scripts/ ./scripts/
COPY --chown=gcsuser:gcsgroup data/processed/ ./data/processed/
COPY --chown=gcsuser:gcsgroup data/output/ ./data/output/
COPY --chown=gcsuser:gcsgroup docs/validation_reports/ ./docs/validation_reports/

# Switch to non-privileged user
USER gcsuser

# Container Healthcheck (Kubernetes / Docker probe)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

EXPOSE 8080

ENTRYPOINT ["python", "scripts/launch_dashboard.py", "--host", "0.0.0.0", "--port", "8080"]
