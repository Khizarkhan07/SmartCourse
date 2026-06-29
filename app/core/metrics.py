import asyncio

from prometheus_client import REGISTRY, Counter, Histogram, push_to_gateway

# 'workflow' label distinguishes which workflow type failed
workflow_failures_total = Counter(
    "workflow_failures_total",
    "Total number of workflow start failures by workflow type",
    ["workflow"],
)

# Buckets cover sub-second fast paths up to 60s for slow email/DB activities
workflow_duration_seconds = Histogram(
    "workflow_duration_seconds",
    "End-to-end workflow execution time from Temporal start to close",
    ["workflow"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0],
)

activity_duration_seconds = Histogram(
    "activity_duration_seconds",
    "Temporal activity execution time in seconds",
    ["activity"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)


async def push_metrics() -> None:
    from app.config import settings  # deferred — Path.expanduser blocked in sandbox
    from app.core.logging import get_logger
    _log = get_logger(__name__)
    try:
        await asyncio.to_thread(
            push_to_gateway, settings.PUSHGATEWAY_URL, "temporal-worker", REGISTRY
        )
        _log.info("metrics pushed to pushgateway", url=settings.PUSHGATEWAY_URL)
    except Exception as exc:
        _log.warning("pushgateway push failed", url=settings.PUSHGATEWAY_URL, error=str(exc))
