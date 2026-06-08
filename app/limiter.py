"""
Shared rate limiter instance.
Instantiated once here and imported everywhere to ensure consistency.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Single shared instance used across the entire app
limiter = Limiter(key_func=get_remote_address)
