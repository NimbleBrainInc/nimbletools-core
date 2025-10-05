"""
Error handling utilities and custom exceptions for NimbleTools Control Plane
"""

import functools
import logging
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from fastapi import HTTPException
from kubernetes.client.rest import ApiException

P = ParamSpec("P")
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger(__name__)


class ControlPlaneError(Exception):
    """Base exception for control plane operations"""

    def __init__(self, message: str, operation: str, resource: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.resource = resource


class KubernetesOperationError(ControlPlaneError):
    """Exception for Kubernetes API operation failures"""

    def __init__(
        self,
        message: str,
        operation: str,
        resource: str,
        api_exception: ApiException | None = None,
    ):
        super().__init__(message, operation, resource)
        self.api_exception = api_exception
        self.status_code = api_exception.status if api_exception else None


def handle_kubernetes_errors(operation: str, resource_type: str) -> Any:
    """
    Decorator to handle Kubernetes API exceptions with proper logging and error conversion.

    Args:
        operation: Description of the operation (e.g., "reading deployment")
        resource_type: Type of Kubernetes resource (e.g., "deployment", "service")
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except ApiException as e:
                # Extract resource identifier from args/kwargs if possible
                resource_id = "unknown"
                if args and len(args) > 1:
                    # Common pattern: first arg after self is resource identifier
                    resource_id = str(args[1])
                elif "name" in kwargs:
                    resource_id = kwargs["name"]
                elif "server_id" in kwargs:
                    resource_id = kwargs["server_id"]

                error_msg = (
                    f"Kubernetes API error while {operation} {resource_type} '{resource_id}'"
                )

                # Log with appropriate level based on status code
                if e.status == 404:
                    logger.info("%s: Resource not found (404)", error_msg)
                elif e.status in (400, 401, 403):
                    logger.warning("%s: Client error (%s): %s", error_msg, e.status, e.reason)
                else:
                    logger.error("%s: Server error (%s): %s", error_msg, e.status, e.reason)
                    if e.body:
                        logger.error("Error details: %s", e.body)

                # Re-raise as domain-specific exception
                raise KubernetesOperationError(
                    message=f"Failed to {operation} {resource_type} '{resource_id}': {e.reason}",
                    operation=operation,
                    resource=f"{resource_type}:{resource_id}",
                    api_exception=e,
                ) from e

            except Exception as e:
                resource_id = "unknown"
                if args and len(args) > 1:
                    resource_id = str(args[1])

                error_msg = (
                    f"Unexpected error while {operation} {resource_type} '{resource_id}': {e}"
                )
                logger.exception(error_msg)

                raise ControlPlaneError(
                    message=f"Failed to {operation} {resource_type} '{resource_id}' due to unexpected error",
                    operation=operation,
                    resource=f"{resource_type}:{resource_id}",
                ) from e

        return wrapper  # type: ignore[return-value]

    return decorator


def handle_optional_kubernetes_resource(
    operation: str, resource_type: str, default_value: Any = None
) -> Any:
    """
    Decorator for operations that may legitimately fail (e.g., reading optional resources).
    Returns default_value instead of raising on 404, but still logs and raises for other errors.

    Args:
        operation: Description of the operation
        resource_type: Type of Kubernetes resource
        default_value: Value to return when resource is not found (default: None)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except ApiException as e:
                resource_id = "unknown"
                if args and len(args) > 1:
                    resource_id = str(args[1])
                elif "name" in kwargs:
                    resource_id = kwargs["name"]

                if e.status == 404:
                    logger.debug(
                        "Optional %s '%s' not found while %s", resource_type, resource_id, operation
                    )
                    return default_value

                # For non-404 errors, use standard error handling
                error_msg = f"Kubernetes API error while {operation} optional {resource_type} '{resource_id}'"

                if e.status in (400, 401, 403):
                    logger.warning("%s: Client error (%s): %s", error_msg, e.status, e.reason)
                else:
                    logger.error("%s: Server error (%s): %s", error_msg, e.status, e.reason)
                    if e.body:
                        logger.error("Error details: %s", e.body)

                raise KubernetesOperationError(
                    message=f"Failed to {operation} optional {resource_type} '{resource_id}': {e.reason}",
                    operation=operation,
                    resource=f"{resource_type}:{resource_id}",
                    api_exception=e,
                ) from e

            except Exception as e:
                resource_id = "unknown"
                if args and len(args) > 1:
                    resource_id = str(args[1])

                error_msg = f"Unexpected error while {operation} optional {resource_type} '{resource_id}': {e}"
                logger.exception(error_msg)

                raise ControlPlaneError(
                    message=f"Failed to {operation} optional {resource_type} '{resource_id}' due to unexpected error",
                    operation=operation,
                    resource=f"{resource_type}:{resource_id}",
                ) from e

        return wrapper  # type: ignore[return-value]

    return decorator


def convert_to_http_exception(error: Exception, default_status_code: int = 500) -> HTTPException:
    """
    Convert domain exceptions to appropriate HTTP exceptions for FastAPI.

    Args:
        error: The exception to convert
        default_status_code: Default HTTP status code if no specific mapping exists
    """
    if isinstance(error, HTTPException):
        return error

    if isinstance(error, KubernetesOperationError):
        api_exc = error.api_exception
        if api_exc:
            if api_exc.status == 404:
                status_code = 404
                detail = f"Resource not found: {error.message}"
            elif api_exc.status in (400, 401, 403):
                status_code = api_exc.status
                detail = error.message
            else:
                status_code = 500
                detail = f"Internal server error: {error.message}"
        else:
            status_code = 500
            detail = f"Internal server error: {error.message}"
        return HTTPException(status_code=status_code, detail=detail)

    # Handle raw Kubernetes ApiException
    if isinstance(error, ApiException):
        if error.status == 404:
            status_code = 404
            detail = "Resource not found"
        elif error.status in (400, 401, 403):
            status_code = error.status
            detail = str(error.reason)
        else:
            status_code = 500
            detail = f"Kubernetes API error: {error.reason}"
        return HTTPException(status_code=status_code, detail=detail)

    if isinstance(error, ControlPlaneError):
        return HTTPException(
            status_code=default_status_code, detail=f"Operation failed: {error.message}"
        )

    # Generic exception
    logger.error("Unhandled exception: %s", error, exc_info=True)
    return HTTPException(status_code=default_status_code, detail="Internal server error occurred")


def log_operation_start(operation: str, resource_type: str, resource_id: str) -> None:
    """Log the start of a significant operation"""
    logger.info("Starting %s for %s '%s'", operation, resource_type, resource_id)


def log_operation_success(operation: str, resource_type: str, resource_id: str) -> None:
    """Log successful completion of an operation"""
    logger.info("Successfully completed %s for %s '%s'", operation, resource_type, resource_id)
