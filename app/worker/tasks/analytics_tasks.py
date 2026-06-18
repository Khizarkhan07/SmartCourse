import asyncio

from app.core.logging import get_logger
from app.worker.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="analytics.invalidate_cache")
def invalidate_analytics_cache_task() -> None:
    """
    Bust all analytics Redis cache keys.
    Called after enrollment or course publish events so the next
    API request re-queries the DB with fresh data.
    """
    from app.infrastructure.cache import cache_delete_pattern

    asyncio.run(cache_delete_pattern("analytics:*"))
    logger.info("analytics cache invalidated")
