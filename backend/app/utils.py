"""
Utility functions and decorators for the DegradeWatch backend.
"""
import logging
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)


def handle_endpoint_errors(func: Callable) -> Callable:
    """
    Decorator to handle common endpoint error logging pattern.

    This decorator wraps endpoint functions to provide consistent error
    logging while preserving the original function's behavior and exceptions.

    Args:
        func: The endpoint function to wrap

    Returns:
        Wrapped function with standardized error handling
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            raise

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            raise

    # Return appropriate wrapper based on function type
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper