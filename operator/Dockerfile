# Multi-stage build for NimbleTools Core Operator
# Uses uv for fast, reproducible builds

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

# Install system dependencies for health checks
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -r -g 1000 app && \
    useradd -r -g app -u 1000 -m -d /app app

# Copy virtual environment from builder
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Set working directory
WORKDIR /app

# Ensure virtual environment is in PATH
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER app

# Health check using Kopf's built-in health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Expose metrics port
EXPOSE 8080

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPERATOR_NAMESPACE=nimbletools-core-system

# Start operator
CMD ["python", "-m", "nimbletools_core_operator.main"]