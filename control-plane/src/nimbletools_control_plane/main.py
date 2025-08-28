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
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Kubernetes client
from kubernetes import config

# Auth system (simplified for community version)
from nimbletools_control_plane.auth import (
    AuthenticatedRequest,
    AuthType,
    UserContext,
    create_auth_provider,
)
from nimbletools_control_plane.models import HealthCheck
from nimbletools_control_plane.routes import (
    registry_router,
    servers_router,
    workspaces_router,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
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
    # Kubernetes config is already loaded at module level
    yield
    # Shutdown: cleanup if needed
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

# Include routers with correct prefixes for ntcli compatibility
app.include_router(workspaces_router)
app.include_router(servers_router)
app.include_router(registry_router)


# Initialize auth provider (pluggable - community uses "none" by default)
auth_provider = create_auth_provider()


# Authentication dependency
async def get_auth_context(request: Request) -> AuthenticatedRequest:
    """Dependency to get authentication context"""
    user_context = await auth_provider.authenticate(request)
    if user_context:
        return AuthenticatedRequest(
            auth_type=(
                AuthType.JWT
                if user_context.get("auth_type") != "none"
                else AuthType.NONE
            ),
            authenticated=True,
            user=UserContext(
                user_id=user_context.get("user_id", "community-user"),
                email=user_context.get("email", "community@nimbletools.dev"),
                role=user_context.get("role", "admin"),
            ),
        )
    return AuthenticatedRequest(auth_type=AuthType.NONE, authenticated=False)


# Simplified auth middleware for community version
@app.middleware("http")
async def auth_middleware(request: Request, call_next: Any) -> Any:
    """Simplified authentication middleware"""
    # Skip auth for health check endpoints
    if request.url.path in [
        "/health",
        "/healthz",
        "/readyz",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/",
    ]:
        response = await call_next(request)
        return response

    # Apply authentication (simplified - community version allows all)
    auth_context = await get_auth_context(request)
    request.state.auth = auth_context

    response = await call_next(request)
    return response


@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint with platform info"""
    return {
        "name": "NimbleTools Control Plane",
        "version": "1.0.0",
        "description": "Control Plane API for workspaces and servers",
        "endpoints": ["/health", "/metrics", "/v1/registry/servers", "/v1/workspaces"],
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
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
