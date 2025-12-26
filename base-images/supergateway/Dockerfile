ARG PYTHON_VERSION=3.14
ARG NODE_VERSION=22

FROM python:${PYTHON_VERSION}-slim

ARG NODE_VERSION

# Install Node.js for supergateway
# Using NodeSource for reliable multi-arch support
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install supergateway globally
RUN npm install -g supergateway

# Install mcpb-loader (stdlib only, no dependencies)
COPY mcpb-loader.py /usr/local/bin/mcpb-loader
RUN chmod 755 /usr/local/bin/mcpb-loader

# Install entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

# Security: non-root user
RUN useradd -m -u 1000 mcpuser

# Create app directory with proper ownership
RUN mkdir -p /app && chown mcpuser:mcpuser /app

USER mcpuser

WORKDIR /app
EXPOSE 8000

# Health check via supergateway's /health endpoint
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
