# Builder stage
FROM python:3.13-slim AS builder

# Install uv via official installer (need curl for installer script)
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin:$PATH"

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

# Copy configuration files
COPY --chown=app:app config /app/config

# Ensure virtual environment is in PATH
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose port
EXPOSE 8080

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PROVIDER_CONFIG=/app/config/community-provider.yaml

# Start API server
CMD ["python", "-m", "nimbletools_control_plane.main"]