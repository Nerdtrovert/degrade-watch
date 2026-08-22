"""
Centralized exception handling for DegradeWatch backend.
Provides custom exception classes and handlers to prevent information leakage
while maintaining debuggability in development environments.
"""

from typing import Any, Dict, Optional
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
import logging
import traceback
import os

logger = logging.getLogger(__name__)

# Determine if we're in debug mode
DEBUG_MODE = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()


class DegradeWatchException(Exception):
    """Base exception for all DegradeWatch custom exceptions."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        internal_message: Optional[str] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.internal_message = internal_message or message
        super().__init__(self.message)


class AuthenticationException(DegradeWatchException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTHENTICATION_ERROR",
            details=details,
            internal_message=message if DEBUG_MODE else "Authentication failed"
        )


class AuthorizationException(DegradeWatchException):
    """Raised when user lacks permission for an action."""

    def __init__(self, message: str = "Insufficient permissions", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="AUTHORIZATION_ERROR",
            details=details,
            internal_message=message if DEBUG_MODE else "Insufficient permissions"
        )


class ValidationException(DegradeWatchException):
    """Raised when input validation fails."""

    def __init__(self, message: str = "Validation failed", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="VALIDATION_ERROR",
            details=details,
            internal_message=message if DEBUG_MODE else "Validation failed"
        )


class NotFoundException(DegradeWatchException):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str = "Resource not found", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND_ERROR",
            details=details,
            internal_message=message if DEBUG_MODE else "Resource not found"
        )


class ConflictException(DegradeWatchException):
    """Raised when there's a conflict with current state."""

    def __init__(self, message: str = "Conflict detected", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            error_code="CONFLICT_ERROR",
            details=details,
            internal_message=message if DEBUG_MODE else "Conflict detected"
        )


class RateLimitException(DegradeWatchException):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="RATE_LIMIT_ERROR",
            details=details,
            internal_message=message if DEBUG_MODE else "Rate limit exceeded"
        )


class ServiceUnavailableException(DegradeWatchException):
    """Raised when a dependent service is unavailable."""

    def __init__(self, message: str = "Service unavailable", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="SERVICE_UNAVAILABLE_ERROR",
            details=details,
            internal_message=message if DEBUG_MODE else "Service unavailable"
        )


class PaymentProcessingException(DegradeWatchException):
    """Raised when payment processing fails."""

    def __init__(self, message: str = "Payment processing failed", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            error_code="PAYMENT_PROCESSING_ERROR",
            details=details,
            internal_message=message if DEBUG_MODE else "Payment processing failed"
        )


class ConfigurationException(DegradeWatchException):
    """Raised when there's a configuration error."""

    def __init__(self, message: str = "Configuration error", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="CONFIGURATION_ERROR",
            details=details,
            internal_message=message if DEBUG_MODE else "Internal server error"
        )


# Exception handlers
async def degradewatch_exception_handler(request: Request, exc: DegradeWatchException) -> JSONResponse:
    """Handle DegradeWatch exceptions and return appropriate JSON response."""
    # Log the exception for debugging (always log full details)
    logger.error(
        f"DegradeWatchException: {exc.__class__.__name__} - {exc.internal_message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method,
            "client_host": request.client.host if request.client else None
        }
    )

    # In debug mode, include internal details; in production, sanitize
    if DEBUG_MODE:
        content = {
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
                "internal_message": exc.internal_message
            }
        }
    else:
        # In production, only return safe information
        content = {
            "error": {
                "code": exc.error_code,
                "message": exc.message
            }
        }
        # Only include details if they're explicitly marked as safe
        if exc.details:
            # Filter out potentially sensitive details
            safe_details = {}
            for key, value in exc.details.items():
                # Only include keys that are known to be safe
                if key in ["timestamp", "request_id", "validation_errors", "available_options"]:
                    safe_details[key] = value
            if safe_details:
                content["error"]["details"] = safe_details

    return JSONResponse(
        status_code=exc.status_code,
        content=content
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle standard HTTPException instances."""
    logger.warning(
        f"HTTPException: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path,
            "method": request.method,
            "client_host": request.client.host if request.client else None
        }
    )

    # For HTTPException, we might want to check if it's already structured
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        # Already structured error
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )

    # Standard HTTPException formatting
    if DEBUG_MODE:
        content = {
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
                "details": {}
            }
        }
    else:
        content = {
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail)
            }
        }

    return JSONResponse(
        status_code=exc.status_code,
        content=content
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    # Always log the full exception for debugging
    logger.error(
        f"Unhandled exception: {type(exc).__name__} - {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "client_host": request.client.host if request.client else None
        },
        exc_info=True  # Include full traceback
    )

    if DEBUG_MODE:
        # In debug mode, show more details
        content = {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(exc),
                "details": {
                    "type": type(exc).__name__,
                    "traceback": traceback.format_exc().splitlines() if os.getenv("FULL_TRACEBACK") else None
                }
            }
        }
    else:
        # In production, never leak internal details
        content = {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred"
            }
        }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content
    )


def setup_exception_handlers(app):
    """Setup exception handlers for the FastAPI application."""
    app.add_exception_handler(DegradeWatchException, degradewatch_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("Exception handlers configured")