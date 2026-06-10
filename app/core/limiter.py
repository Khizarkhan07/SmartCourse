"""Shared rate limiter instance for API endpoints.

Instantiated once here and imported everywhere to ensure consistency.
Used to enforce rate limits on endpoints (e.g., login, password reset).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Single shared instance used across the entire app
limiter = Limiter(key_func=get_remote_address)

__all__ = ["limiter"]
