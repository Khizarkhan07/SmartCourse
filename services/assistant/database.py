from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings

engine = create_async_engine(settings.DATABASE_URL, pool_size=5, max_overflow=10)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Sync engine for background worker threads (ingestion, Kafka consumers) —
# asyncpg cannot be used outside an asyncio event loop.
sync_engine = create_engine(settings.DATABASE_URL_SYNC, pool_size=5, max_overflow=10)
SyncSessionLocal = sessionmaker(sync_engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
