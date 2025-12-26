# MCPB Binary Runtime
# Minimal image for running pre-compiled MCP server binaries
FROM debian:bookworm-slim

# Install minimal dependencies for bundle download and extraction
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

# Create non-root user
RUN useradd -m -u 1000 mcpuser
RUN mkdir -p /app && chown mcpuser:mcpuser /app

USER mcpuser
WORKDIR /app

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
