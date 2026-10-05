# ──────────────────────────────────────────────────────────────
# GEISER Backend — Production Dockerfile
# FastAPI + Uvicorn (Python 3.11 slim)
# ──────────────────────────────────────────────────────────────

FROM python:3.11-slim

# System dependencies for faiss-cpu, sentence-transformers, ldap3, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libopenblas-dev \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN useradd --create-home --shell /bin/bash geiser

WORKDIR /app

# Install Python dependencies first (layer-cached)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source (excluding secrets, see .dockerignore)
COPY . .

# Create persistent data directories and set ownership
RUN mkdir -p /app/uploads /app/storage/faiss /app/backups /app/logs \
    && chown -R geiser:geiser /app

USER geiser

# Expose API port
EXPOSE 8000

# Health check — uses the lightweight /health endpoint (no Ollama dependency)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production entrypoint — no --reload, bound to 0.0.0.0
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--log-level", "info"]
