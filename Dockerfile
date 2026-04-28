# syntax=docker/dockerfile:1.6

# ---------- Stage 1: builder ----------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install Python dependencies into an isolated prefix so we can copy them
# into the runtime image without dragging in pip's caches or build tools.
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    HOST=0.0.0.0 \
    PORT=5000

# Create non-root user up front so we can chown during COPY.
# Install gosu so the entrypoint can drop from root to the app user.
RUN useradd -m -u 1000 app \
    && apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed Python packages from the builder stage
COPY --from=builder /install /usr/local

# Copy application code with correct ownership
COPY --chown=app:app backend/ backend/
COPY --chown=app:app frontend/ frontend/
COPY --chown=app:app run.py .

# Create writable data directories owned by the app user
RUN mkdir -p instance uploads/downloads temp \
    && chown -R app:app /app

# Copy the entrypoint shim. It runs as root, fixes volume ownership when
# upgrading from v0.3.4 (root-owned files), then drops to the app user via gosu.
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

LABEL org.opencontainers.image.source="https://github.com/CTR-TRANSCEND/research-pdf-renamer"
LABEL org.opencontainers.image.description="Research PDF File Renamer - AI-powered PDF renaming tool"
LABEL org.opencontainers.image.licenses="MIT"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "12", \
     "--worker-class", "gthread", "--timeout", "600", "--access-logfile", "-", \
     "--error-logfile", "-", "backend.app:create_app('production')"]
