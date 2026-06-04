
from temporalio.client import Client

# Dedicated queues to isolate different workload types at scale.
ENROLLMENT_TASK_QUEUE = "smartcourse-enrollment-queue"
COURSE_TASK_QUEUE = "smartcourse-course-queue"
NOTIFICATION_TASK_QUEUE = "smartcourse-notification-queue"

# Legacy alias kept for older scripts/tests that still import TASK_QUEUE.
TASK_QUEUE = ENROLLMENT_TASK_QUEUE

# Module-level cache — None until first call
_client: Client | None = None


async def get_temporal_client() -> Client:
    """Return a cached Temporal client, connecting on first call."""
    global _client
    if _client is None:
        _client = await Client.connect("localhost:7233")
    return _client
