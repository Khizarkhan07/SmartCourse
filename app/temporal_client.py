
from temporalio.client import Client

TASK_QUEUE = "smartcourse-queue"

# Module-level cache — None until first call
_client: Client | None = None


async def get_temporal_client() -> Client:
    """Return a cached Temporal client, connecting on first call."""
    global _client
    if _client is None:
        _client = await Client.connect("localhost:7233")
    return _client
