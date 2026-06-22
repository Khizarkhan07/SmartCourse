import redis.asyncio as aioredis

from config import settings

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


async def blacklist_token(jti: str, ttl_seconds: int) -> None:
    await get_redis().setex(f"token:blacklist:{jti}", ttl_seconds, "1")


async def is_token_blacklisted(jti: str) -> bool:
    return await get_redis().exists(f"token:blacklist:{jti}") > 0
