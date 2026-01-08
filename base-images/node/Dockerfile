ARG NODE_VERSION=24

FROM node:${NODE_VERSION}-alpine

# Minimal base image - all dependencies come from the MCPB bundle
# This ensures bundles are fully portable and self-contained

# Install unzip for bundle extraction
RUN apk add --no-cache unzip bash

# Install mcpb-loader
COPY mcpb-loader.js /usr/local/bin/mcpb-loader
RUN chmod 755 /usr/local/bin/mcpb-loader

# Install entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

# Create app directory with proper ownership
RUN mkdir -p /home/node/app && chown node:node /home/node/app

# Security: use existing 'node' user (UID 1000 in node:alpine images)
USER node

WORKDIR /home/node/app
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
