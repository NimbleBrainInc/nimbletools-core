# Multi-stage build for NimbleTools Universal Adapter
# Uses uv for fast, reproducible builds with dynamic package management

# Builder stage
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies into .venv
RUN uv sync --frozen --no-dev

# Copy source code
COPY src ./src

# Install the package
RUN uv pip install --no-deps .

# Runtime stage
FROM python:3.13-slim AS runtime

# Install system dependencies for universal package management
RUN apt-get update && apt-get install -y \
    curl \
    git \
    gnupg \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install Node.js LTS (minimal installation)
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest \
    && rm -rf /var/lib/apt/lists/*

# Configure npm globally for efficient package management
RUN npm config set cache /tmp/npm-cache \
    && npm config set fund false \
    && npm config set audit false

# Create non-root user
RUN groupadd -r -g 1000 app && \
    useradd -r -g app -u 1000 -m -d /app app

# Copy virtual environment from builder
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Create directories for config
RUN mkdir -p /config && chown -R app:app /config

# Set working directory
WORKDIR /app

# Ensure virtual environment is in PATH
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER app

# Configure npm for the non-root user
RUN npm config set cache /tmp/npm-cache \
    && npm config set fund false \
    && npm config set audit false \
    && npm config set prefix /tmp/npm-global

# Set PATH to include npm global binaries and environment
ENV PATH="/tmp/npm-global/bin:$PATH" \
    HOME="/home/app" \
    NPM_CONFIG_CACHE="/tmp/npm-cache" \
    NPM_CONFIG_PREFIX="/tmp/npm-global" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Start universal adapter
CMD ["python", "-m", "nimbletools_universal_adapter.main"]