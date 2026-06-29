from temporalio.client import Client
from config import settings


async def get_temporal_client() -> Client:
    return await Client.connect(settings.TEMPORAL_HOST)
