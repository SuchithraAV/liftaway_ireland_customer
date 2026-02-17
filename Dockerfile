# =========================
# Builder Stage
# =========================
FROM python:3.11-slim AS builder

# Set environment variables
ENV POETRY_VERSION=1.7.1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}

# Copy only dependency files first (for better caching)
COPY pyproject.toml poetry.lock* ./

# Install dependencies (NO dev dependencies)
RUN poetry install --only main --no-root

# =========================
# Runtime Stage
# =========================
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Set working directory
WORKDIR /app

# Install runtime OS dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source code
COPY . .

# Copy production env as .env (will be overridden by Docker env vars if provided)
COPY .env.production .env

# Create non-root user
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh && chown appuser:appuser /usr/local/bin/docker-entrypoint.sh

# Switch to non-root user
USER appuser

# Expose application port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/')" || exit 1

# Use entrypoint script
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
