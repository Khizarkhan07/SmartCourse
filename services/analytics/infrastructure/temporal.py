from temporalio.client import Client

_client: Client | None = None


async def get_temporal_client() -> Client:
    from config import settings
    global _client
    if _client is None:
        _client = await Client.connect(settings.TEMPORAL_HOST)
    return _client
