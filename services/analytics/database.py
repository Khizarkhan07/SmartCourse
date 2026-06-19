from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from config import settings

# Async engine — used by the FastAPI API
engine = create_async_engine(settings.DATABASE_URL, pool_size=5, max_overflow=10)
AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

# Sync engine — used by Kafka consumers (blocking threads, no async needed)
sync_engine = create_engine(settings.DATABASE_URL_SYNC, pool_size=5, max_overflow=10)
SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False, class_=Session)


class Base(DeclarativeBase):
    pass
