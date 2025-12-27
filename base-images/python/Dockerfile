ARG PYTHON_VERSION=3.14

FROM python:${PYTHON_VERSION}-slim

# Minimal base image - all dependencies come from the MCPB bundle
# This ensures bundles are fully portable and self-contained

# Install mcpb-loader
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

HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

ENTRYPOINT ["/entrypoint.sh"]
