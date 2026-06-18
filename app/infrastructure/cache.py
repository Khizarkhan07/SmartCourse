import json
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


async def cache_get(key: str) -> Any | None:
    value = await get_redis().get(key)
    if value is None:
        return None
    return json.loads(value)


async def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    # default=str handles date/UUID objects that aren't JSON-serializable natively
    await get_redis().setex(key, ttl, json.dumps(value, default=str))


async def cache_delete(key: str) -> None:
    await get_redis().delete(key)


async def cache_delete_pattern(pattern: str) -> None:
    keys = await get_redis().keys(pattern)
    if keys:
        await get_redis().delete(*keys)


async def blacklist_token(jti: str, ttl_seconds: int) -> None:
    # TTL matches the token's remaining lifetime — key auto-expires when token would have anyway
    await get_redis().setex(f"token:blacklist:{jti}", ttl_seconds, "1")


async def is_token_blacklisted(jti: str) -> bool:
    return await get_redis().exists(f"token:blacklist:{jti}") > 0
