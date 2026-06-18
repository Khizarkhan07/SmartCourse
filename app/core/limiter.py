from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

# storage_uri switches slowapi from in-memory (per-process, resets on restart)
# to Redis (shared across restarts and multiple API instances)
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)

__all__ = ["limiter"]
