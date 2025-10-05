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

# Install UV for Python package management (includes both uv and uvx)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY --from=ghcr.io/astral-sh/uv:latest /uvx /usr/local/bin/uvx
RUN uv --version && uvx --version

# Configure npm globally for efficient package management
RUN npm config set cache /tmp/npm-cache \
    && npm config set fund false \
    && npm config set audit false

# Create non-root user with home at /home/app (not /app to avoid npm config conflicts)
RUN groupadd -r -g 1000 app && \
    useradd -r -g app -u 1000 -m -d /home/app app

# Copy virtual environment from builder
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Create directories for config
RUN mkdir -p /config && chown -R app:app /config

# Switch to non-root user
USER app

# Configure npm for the non-root user (creates .npmrc in home directory)
# Use /home/app/.npm for cache instead of /tmp to persist across container restarts
RUN mkdir -p /home/app/.npm /home/app/.npm-global && \
    npm config set cache /home/app/.npm \
    && npm config set fund false \
    && npm config set audit false \
    && npm config set prefix /home/app/.npm-global

# Set working directory AFTER npm config (so .npmrc goes to home, not /app)
WORKDIR /app

# Ensure virtual environment is in PATH
ENV PATH="/app/.venv/bin:$PATH"

# Set PATH to include npm global binaries and environment
ENV PATH="/home/app/.npm-global/bin:$PATH" \
    HOME="/home/app" \
    NPM_CONFIG_CACHE="/home/app/.npm" \
    NPM_CONFIG_PREFIX="/home/app/.npm-global" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Pre-warm npm cache to verify npm/npx work
# Universal adapter handles package installation at runtime
RUN npx --yes cowsay@1.6.0 "Cache ready" > /dev/null 2>&1 || true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Start universal adapter
CMD ["python", "-m", "nimbletools_universal_adapter.main"]