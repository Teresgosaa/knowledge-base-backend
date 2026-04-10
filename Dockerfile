# =============================================================================
# Dockerfile
# =============================================================================
FROM python:3.12.12-slim-bookworm AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
    # ✅ Removed UV_PREFER_BINARY=1 (not a valid uv env var)

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libpq-dev \
    pkg-config \
    protobuf-compiler \
    libprotoc-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency files first (for better layer caching)
COPY pyproject.toml uv.lock* ./

# ✅ Fixed: Removed --prefer-binary (not supported by uv)
# uv already prefers binaries by default
RUN if [ -f "uv.lock" ]; then \
        uv pip install --system --no-cache-dir -e .; \
    elif [ -f "pyproject.toml" ]; then \
        uv pip install --system --no-cache-dir -e .; \
    fi

# =============================================================================
# Runtime stage
# =============================================================================
FROM python:3.14.2-slim-bookworm AS runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    APP_HOME=/app \
    TZ=UTC

# Install system dependencies required by your packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code with correct ownership
COPY --chown=appuser:appuser . .

# Create required directories and set permissions
RUN mkdir -p /app/app/static /app/app/templates /cert /app/logs && \
    chown -R appuser:appuser /app /cert /app/logs

# Switch to non-root user
USER appuser

EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ✅ Fixed CMD: use uvicorn directly
CMD ["uvicorn", "app.application:get_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]