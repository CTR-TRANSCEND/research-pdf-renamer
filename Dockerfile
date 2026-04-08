FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies (all packages have pre-built wheels)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ backend/
COPY frontend/ frontend/
COPY run.py .

# Create directories for data persistence
RUN mkdir -p instance uploads/downloads temp

# Default environment
ENV FLASK_ENV=production \
    HOST=0.0.0.0 \
    PORT=5000

EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

LABEL org.opencontainers.image.source="https://github.com/CTR-TRANSCEND/research-pdf-renamer"
LABEL org.opencontainers.image.description="Research PDF File Renamer - AI-powered PDF renaming tool"
LABEL org.opencontainers.image.licenses="MIT"

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--threads", "4", \
     "--worker-class", "gthread", "--timeout", "300", "--access-logfile", "-", \
     "--error-logfile", "-", "backend.app:create_app('production')"]
