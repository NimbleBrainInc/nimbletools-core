#!/usr/bin/env python3
"""
NimbleTools Control Plane
"""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Kubernetes client
from kubernetes import config

# Provider system
from nimbletools_control_plane import provider
from nimbletools_control_plane.models import HealthCheck
from nimbletools_control_plane.route_loader import load_routes

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# Initialize Kubernetes client configuration at module level
try:
    config.load_incluster_config()
    logger.info("Loaded in-cluster Kubernetes configuration")
except config.ConfigException:
    try:
        config.load_kube_config()
        logger.info("Loaded local Kubernetes configuration")
    except config.ConfigException:
        logger.error("Could not load Kubernetes configuration")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown"""
    logger.info("Starting NimbleTools Control Plane")

    # Initialize providers
    await provider.initialize()

    yield

    # Shutdown providers
    await provider.shutdown()
    logger.info("Shutting down NimbleTools Control Plane")


app = FastAPI(
    title="NimbleTools Control Plane",
    description=f"Control Plane API for workspaces and servers (api.{os.getenv('DOMAIN', 'nimbletools.local')})",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dynamically load all route modules
load_routes(app)


@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint with platform info"""
    return {
        "name": "NimbleTools Control Plane",
        "version": "1.0.0",
        "description": "Control Plane API for workspaces and servers",
        "endpoints": ["/health", "/metrics", "/v1/workspaces", "/v1/servers"],
        "mcp_runtime": f"mcp.{os.getenv('DOMAIN', 'nimbletools.local')}/{{workspace_id}}/{{server_id}}/mcp",
    }


@app.get("/health")
async def health_check() -> HealthCheck:
    """Health check endpoint"""
    return HealthCheck(
        status="healthy",
        version="0.1.0",
        service="Powered by NimbleTools.ai",
        timestamp=datetime.now(UTC),
    )


def main() -> None:
    """Main entry point for the application."""
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="debug")


if __name__ == "__main__":
    main()
