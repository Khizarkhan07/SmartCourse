"""Temporal server connection and task queue configuration.

Dedicated queues isolate different workload types at scale:
- ENROLLMENT_TASK_QUEUE: User enrollments and onboarding
- COURSE_TASK_QUEUE: Course state transitions (publish, archive)
- NOTIFICATION_TASK_QUEUE: Email and notification activities
"""

from temporalio.client import Client
from app.config import settings

# Dedicated queues to isolate different workload types at scale.
ENROLLMENT_TASK_QUEUE = "smartcourse-enrollment-queue"
COURSE_TASK_QUEUE = "smartcourse-course-queue"
NOTIFICATION_TASK_QUEUE = "smartcourse-notification-queue"

# Module-level cache — None until first call
_client: Client | None = None


async def get_temporal_client() -> Client:
    """Return a cached Temporal client, connecting on first call."""
    global _client
    if _client is None:
        _client = await Client.connect(settings.TEMPORAL_HOST)
    return _client


__all__ = [
    "get_temporal_client",
    "ENROLLMENT_TASK_QUEUE",
    "COURSE_TASK_QUEUE",
    "NOTIFICATION_TASK_QUEUE",
]
