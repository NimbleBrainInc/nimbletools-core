#!/usr/bin/env python3
"""
Universal MCP Adapter - Dynamic Package Management
Provides HTTP/JSON-RPC interface for any MCP server with just-in-time package installation
Memory efficient, extensible, and configuration-driven
"""

import asyncio
import contextlib
import json
import logging
import os
import shlex
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PackageSpec(BaseModel):
    """Package specification for dynamic installation"""

    type: str  # npm, github, local, or executable
    source: str  # package name, repo URL, or path
    version: str | None = None
    install_args: list[str] = []


class ServerConfig(BaseModel):
    """Universal server configuration supporting multiple deployment types"""

    name: str
    executable: str
    args: list[str]
    working_dir: str
    environment: dict[str, str] = {}
    package: PackageSpec | None = None


class PackageManager:
    """Dynamic package management with memory optimization"""

    def __init__(self):
        self.installed_packages: dict[str, str] = {}
        self.cache_dir = Path("/tmp/npm-cache")
        self.install_dir = Path("/tmp/mcp-packages")
        self.install_dir.mkdir(exist_ok=True)

    async def install_package(self, package_spec: PackageSpec) -> bool:
        """Install package dynamically based on type"""
        cache_key = f"{package_spec.type}:{package_spec.source}"

        if cache_key in self.installed_packages:
            logger.info("📦 Package already installed: %s", cache_key)
            return True

        logger.info("📥 Installing package: %s - %s", package_spec.type, package_spec.source)

        try:
            if package_spec.type == "npm":
                success = await self._install_npm_package(package_spec)
            elif package_spec.type == "github":
                success = await self._install_github_package(package_spec)
            elif package_spec.type == "executable":
                success = await self._verify_executable(package_spec)
            else:
                logger.error("❌ Unsupported package type: %s", package_spec.type)
                return False

            if success:
                self.installed_packages[cache_key] = package_spec.source
                logger.info("✅ Package installed successfully: %s", cache_key)

            return success

        except Exception as e:
            logger.error("❌ Package installation failed: %s", e)
            return False

    async def _install_npm_package(self, spec: PackageSpec) -> bool:
        """Install npm package with memory optimization"""
        try:
            package_name = spec.source
            if spec.version:
                package_name = f"{package_name}@{spec.version}"

            # Use npx for one-time execution or npm install for persistence
            if spec.install_args and "--global" in spec.install_args:
                cmd = ["npm", "install", "-g", package_name]
            else:
                # Install locally in temp directory
                install_path = self.install_dir / spec.source.replace("/", "-")
                install_path.mkdir(exist_ok=True, parents=True)
                cmd = ["npm", "install", package_name]

            cmd.extend(spec.install_args)

            # Set environment to ensure proper permissions for npm cache
            env = os.environ.copy()
            env.update(
                {
                    "NPM_CONFIG_CACHE": "/tmp/npm-cache-user",
                    "HOME": "/tmp/home-user",
                }
            )

            result = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=install_path if "install_path" in locals() else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                logger.debug("NPM install output: %s", stdout.decode())
                return True
            else:
                logger.error("NPM install failed: %s", stderr.decode())
                return False

        except Exception as e:
            logger.error("NPM installation error: %s", e)
            return False

    async def _install_github_package(self, spec: PackageSpec) -> bool:
        """Clone and setup GitHub repository"""
        try:
            repo_name = spec.source.split("/")[-1].replace(".git", "")
            clone_path = self.install_dir / repo_name

            if clone_path.exists():
                logger.info("Repository already cloned: %s", clone_path)
                return True

            # Clone repository
            cmd = ["git", "clone", "--depth", "1", spec.source, str(clone_path)]
            if spec.version:
                cmd.extend(["--branch", spec.version])

            result = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                logger.error("Git clone failed: %s", stderr.decode())
                return False

            # Install dependencies if package.json exists
            package_json = clone_path / "package.json"
            if package_json.exists():
                install_result = await asyncio.create_subprocess_exec(
                    "npm",
                    "install",
                    cwd=clone_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await install_result.communicate()

            return True

        except Exception as e:
            logger.error("GitHub installation error: %s", e)
            return False

    async def _verify_executable(self, spec: PackageSpec) -> bool:
        """Verify executable is available"""
        try:
            result = await asyncio.create_subprocess_exec(
                "which",
                spec.source,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await result.communicate()
            return result.returncode == 0

        except Exception as e:
            logger.error("Executable verification error: %s", e)
            return False

    def cleanup_packages(self):
        """Cleanup installed packages to free memory"""
        try:
            # Clear npm cache
            subprocess.run(["npm", "cache", "clean", "--force"], check=False)

            # Remove temporary installations
            if self.install_dir.exists():
                subprocess.run(["rm", "-rf", str(self.install_dir)], check=False)
                self.install_dir.mkdir(exist_ok=True)

            logger.info("🧹 Package cleanup completed")

        except Exception as e:
            logger.warning("Package cleanup warning: %s", e)


class UniversalMCPAdapter:
    """Universal adapter for any MCP server with dynamic package management"""

    def __init__(self):
        self.config: ServerConfig | None = None
        self.process: subprocess.Popen | None = None
        self.startup_time = time.time()
        self.process_lock = asyncio.Lock()
        self.package_manager = PackageManager()
        self.capabilities: dict[str, list[Any]] = {"tools": [], "resources": [], "prompts": []}

        # Load configuration
        self._load_config()

    def _load_config(self):
        """Load universal server configuration from environment variables"""
        try:
            # Read configuration from environment variables set by the operator
            server_name = os.getenv("MCP_SERVER_NAME", "unknown-server")
            executable = os.getenv("MCP_EXECUTABLE")
            args_str = os.getenv("MCP_ARGS", "")
            working_dir = os.getenv("MCP_WORKING_DIR", "/tmp")

            if not executable:
                raise ValueError("MCP_EXECUTABLE environment variable is required")

            # Parse arguments from JSON or comma-separated string
            if args_str:
                try:
                    # Try parsing as JSON array first
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    # Fall back to comma-separated string
                    args = [arg.strip() for arg in args_str.split(",") if arg.strip()]
            else:
                args = []

            # Load capabilities from environment (set by operator from registry)
            tools_str = os.getenv("MCP_TOOLS", "[]")
            resources_str = os.getenv("MCP_RESOURCES", "[]")
            prompts_str = os.getenv("MCP_PROMPTS", "[]")

            try:
                tools = json.loads(tools_str)
                resources = json.loads(resources_str)
                prompts = json.loads(prompts_str)
                self.capabilities = {"tools": tools, "resources": resources, "prompts": prompts}
            except json.JSONDecodeError:
                logger.warning("Failed to parse MCP capabilities, using empty capabilities")
                self.capabilities = {"tools": [], "resources": [], "prompts": []}

            # Create server configuration
            self.config = ServerConfig(
                name=server_name,
                executable=executable,
                args=args,
                working_dir=working_dir,
                environment=self._get_forwarded_environment(),
            )

            logger.info("✅ Loaded universal configuration for %s", self.config.name)
            logger.info("📁 Executable: %s %s", executable, ' '.join(args))
            logger.info("📁 Working directory: %s", working_dir)
            logger.info(
                "📋 Server capabilities: tools=%d, resources=%d, prompts=%d",
                len(self.capabilities['tools']),
                len(self.capabilities['resources']),
                len(self.capabilities['prompts'])
            )

        except Exception as e:
            logger.error("❌ Failed to load config: %s", e)
            raise RuntimeError(f"Configuration loading failed: {e}") from e

    def _get_forwarded_environment(self) -> dict[str, str]:
        """Get environment variables that should be forwarded to the MCP server"""
        forwarded_vars = {}

        # Forward API keys and configuration
        env_patterns = [
            "NPS_API_KEY",
            "API_KEY",
            "OPENAI_API_KEY",
            "LOG_LEVEL",
            "NODE_ENV",
            "DEBUG",
        ]

        for pattern in env_patterns:
            if pattern in os.environ:
                forwarded_vars[pattern] = os.environ[pattern]

        # Also forward any environment variable starting with MCP_ENV_
        for key, value in os.environ.items():
            if key.startswith("MCP_ENV_"):
                # Remove MCP_ENV_ prefix when forwarding
                actual_key = key[8:]  # Remove "MCP_ENV_"
                forwarded_vars[actual_key] = value

        return forwarded_vars

    def _detect_package_spec(self, executable: str, args: list[str]) -> PackageSpec | None:
        """Detect package requirements from executable and args"""
        if executable == "npx" and args:
            # Handle npx -y package-name format - no installation needed, npx handles it
            if "-y" in args:
                # npx -y means auto-install, so we just verify npx is available
                return PackageSpec(type="executable", source="npx")

            # Handle direct package name
            if args and not args[0].startswith("-"):
                return PackageSpec(type="npm", source=args[0], install_args=[])

        elif executable.startswith("npm") and "install" in args:
            # Direct npm install command
            return PackageSpec(
                type="npm",
                source="unknown",  # Will be handled by npm directly
                install_args=args,
            )

        # For other executables, assume they're system executables
        return PackageSpec(type="executable", source=executable)

    def _supports_resources(self) -> bool:
        """Check if server supports resources based on capabilities"""
        return len(self.capabilities.get("resources", [])) > 0

    def _supports_prompts(self) -> bool:
        """Check if server supports prompts based on capabilities"""
        return len(self.capabilities.get("prompts", [])) > 0

    def _supports_tools(self) -> bool:
        """Check if server supports tools based on capabilities"""
        return len(self.capabilities.get("tools", [])) > 0

    async def initialize(self):
        """Initialize the adapter with package installation"""
        if not self.config:
            raise RuntimeError("Configuration not loaded")

        # Detect and install required package based on executable and args
        package_spec = self._detect_package_spec(self.config.executable, self.config.args)
        if package_spec:
            logger.info(
                "📦 Detected package requirement: %s - %s",
                package_spec.type,
                package_spec.source
            )
            success = await self.package_manager.install_package(package_spec)
            if not success:
                raise RuntimeError(f"Failed to install required package: {package_spec.source}")

        # Start the MCP server process
        await self._start_process()

        logger.info("🚀 Universal adapter initialized for %s", self.config.name)

    async def _start_process(self):
        """Start the universal MCP server process"""
        if not self.config:
            raise RuntimeError("No configuration available")

        # Prepare environment
        env = os.environ.copy()
        env.update(self.config.environment)

        # Fix npm cache permissions for npx commands
        if self.config.executable == "npx":
            env.update(
                {
                    "NPM_CONFIG_CACHE": "/tmp/npm-cache-user",
                    "HOME": "/tmp/home-user",
                    "npm_config_cache": "/tmp/npm-cache-user",
                }
            )

        # Build command with proper shell escaping
        full_command = [self.config.executable, *self.config.args]
        safe_command = " ".join(shlex.quote(arg) for arg in full_command)

        logger.info("🚀 Starting universal MCP server: %s", safe_command)
        logger.info("📁 Working directory: %s", self.config.working_dir)
        logger.info("🔑 Environment variables: %s", list(self.config.environment.keys()))

        try:
            self.process = subprocess.Popen(
                full_command,
                cwd=self.config.working_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                bufsize=0,  # Unbuffered for real-time communication
            )

            # Give the process a moment to start
            await asyncio.sleep(3)

            if self.process.poll() is None:
                logger.info("✅ Universal MCP server started successfully")
            else:
                stderr_output = ""
                if self.process.stderr:
                    stderr_output = self.process.stderr.read()
                raise RuntimeError(f"Universal MCP server failed to start. Stderr: {stderr_output}")

        except Exception as e:
            logger.error("❌ Failed to start universal MCP server: %s", e)
            raise

    async def send_request(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send JSON-RPC request to stdio MCP server"""
        async with self.process_lock:
            if not self.process or self.process.poll() is not None:
                logger.warning("🔄 Process not running, attempting restart...")
                await self._restart_process()

                if not self.process or self.process.poll() is not None:
                    raise RuntimeError(
                        "Universal MCP server process is not running and restart failed"
                    )

            try:
                # Send JSON-RPC message
                request_json = json.dumps(message) + "\n"
                logger.debug("📤 Sending: %s", request_json.strip())

                self.process.stdin.write(request_json)
                self.process.stdin.flush()

                # Read response with timeout
                response_line = await asyncio.wait_for(
                    asyncio.to_thread(self.process.stdout.readline), timeout=30.0
                )

                if not response_line:
                    raise RuntimeError("No response from stdio MCP server")

                logger.debug("📥 Received: %s", response_line.strip())
                response = json.loads(response_line.strip())
                return response

            except TimeoutError:
                logger.error("❌ Request timeout")
                raise RuntimeError("Request timeout - stdio server not responding") from None
            except json.JSONDecodeError as e:
                logger.error("❌ Invalid JSON response: %s", response_line)
                raise RuntimeError(f"Invalid JSON response from stdio server: {e}") from e
            except Exception as e:
                logger.error("❌ Stdio communication failed: %s", e)
                raise RuntimeError(f"Communication failed: {e}") from e

    async def _restart_process(self):
        """Restart universal MCP server process if it fails"""
        logger.warning("🔄 Restarting universal MCP server process")

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                with contextlib.suppress(Exception):
                    self.process.kill()
                    self.process.wait(timeout=2)

        # Restart
        await self._start_process()

    def is_healthy(self) -> bool:
        """Check if the stdio process is healthy"""
        return self.process is not None and self.process.poll() is None

    def cleanup(self):
        """Cleanup resources and installed packages"""
        # Stop the MCP server process
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                with contextlib.suppress(Exception):
                    self.process.kill()
            finally:
                self.process = None

        # Cleanup installed packages to free memory
        self.package_manager.cleanup_packages()
        logger.info("🧹 Universal adapter cleanup completed")


# Create FastAPI app
app = FastAPI(title="Universal MCP Adapter", version="3.0.0")

# Global adapter instance - initialized on startup
adapter: UniversalMCPAdapter | None = None


@app.on_event("startup")
async def startup_event():
    """Initialize universal adapter on startup"""
    global adapter  # noqa: PLW0603
    try:
        adapter = UniversalMCPAdapter()
        await adapter.initialize()
        logger.info("🚀 Universal MCP Adapter started successfully")
    except Exception as e:
        logger.error("❌ Failed to start universal adapter: %s", e)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if adapter is not None:
        adapter.cleanup()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if not adapter or not adapter.config:
        raise HTTPException(status_code=503, detail="Universal adapter not initialized")

    # Get package information
    package_info = {}
    if adapter.config.package:
        package_info = {
            "type": adapter.config.package.type,
            "source": adapter.config.package.source,
            "installed": len(adapter.package_manager.installed_packages) > 0,
        }

    return {
        "status": "healthy" if adapter.is_healthy() else "degraded",
        "service": f"universal-adapter-{adapter.config.name}",
        "uptime": time.time() - adapter.startup_time,
        "process_running": adapter.is_healthy(),
        "config": {
            "executable": adapter.config.executable,
            "args": adapter.config.args,
            "working_dir": adapter.config.working_dir,
            "package": package_info,
        },
        "capabilities": {
            "tools": len(adapter.capabilities.get("tools", [])),
            "resources": len(adapter.capabilities.get("resources", [])),
            "prompts": len(adapter.capabilities.get("prompts", [])),
        },
        "installed_packages": list(adapter.package_manager.installed_packages.keys()),
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "3.0.0",
    }


def _create_error_response(request_id: str | None, code: int, message: str) -> dict[str, Any]:
    """Create a standardized JSON-RPC error response"""
    return {
        "jsonrpc": "2.0",
        "id": request_id or "unknown",
        "error": {"code": code, "message": message},
    }




@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP protocol endpoint - handles all JSON-RPC methods"""
    if not adapter:
        raise HTTPException(status_code=503, detail="Adapter not initialized")

    try:
        request_data = await request.json()
        method = request_data.get("method", "unknown")
        request_id = request_data.get("id")

        logger.info("🔄 MCP request: %s (repr: %r)", method, method)

        return await _route_method(request_data, adapter)

    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400,
            content=_create_error_response("unknown", -32700, "Parse error"),
        )
    except Exception as e:
        logger.error("MCP endpoint error: %s", e)
        return JSONResponse(
            status_code=500,
            content=_create_error_response(
                request_data.get("id", "unknown") if "request_data" in locals() else "unknown",
                -32603,
                f"Internal error: {e!s}",
            ),
        )


async def _route_method(
    request_data: dict[str, Any], adapter: UniversalMCPAdapter
) -> dict[str, Any] | Response:
    """Route method to appropriate handler based on method type"""
    method = request_data.get("method", "unknown")
    request_id = request_data.get("id")

    # Handle initialize method locally (don't forward to stdio server)
    if method == "initialize":
        return await _handle_initialize(request_data, adapter)

    # Handle notifications (don't forward, no response needed)
    if method in ["notifications/initialized", "initialized", "notifications/cancelled"]:
        logger.info("✅ MCP notification handled locally - method: %s", method)
        return Response(status_code=200)

    # Handle capability-based methods - always forward to underlying server
    if method.startswith(("resources/", "prompts/", "tools/")):
        logger.info("🔄 Capability method '%s' - forwarding to stdio server", method)
        try:
            response = await adapter.send_request(request_data)
            logger.debug("✅ Capability method '%s' completed successfully", method)
            return response
        except Exception as e:
            logger.error("❌ Failed to forward capability method '%s': %s", method, e)
            return _create_error_response(request_id, -32603, f"Internal server error: {e!s}")

    # Handle unknown methods
    logger.info("❓ Unknown method '%s' - returning method not supported", method)
    return _create_error_response(
        request_id, -32601, f"Method '{method}' not supported by this server"
    )


async def _handle_initialize(
    request_data: dict[str, Any], adapter: UniversalMCPAdapter
) -> dict[str, Any]:
    """Handle the initialize method"""
    client_info = request_data.get("params", {}).get("clientInfo", {})
    logger.info("🤝 Initializing MCP connection - Client: %s", client_info)

    # Build dynamic capabilities based on server configuration
    server_capabilities = {}
    if adapter._supports_tools():
        server_capabilities["tools"] = {}
    if adapter._supports_resources():
        server_capabilities["resources"] = {}
    if adapter._supports_prompts():
        server_capabilities["prompts"] = {}

    return {
        "jsonrpc": "2.0",
        "id": request_data.get("id"),
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": server_capabilities,
            "serverInfo": {"name": adapter.config.name, "version": "3.0.0"},
        },
    }


def main() -> None:
    """Main entry point for the universal adapter."""
    port = int(os.getenv("PORT", "8000"))
    logger.info("Starting Universal MCP Adapter on port %s", port)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
