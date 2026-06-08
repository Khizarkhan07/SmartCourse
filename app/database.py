from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# The engine manages the connection pool to PostgreSQL
# pool_size: number of persistent connections kept open
# max_overflow: extra connections allowed beyond pool_size during spikes
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    echo=(settings.APP_ENV == "development"),  # logs SQL queries in dev only
)

# Session factory — call this to get a database session per request
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keep objects readable after commit
)


# All SQLAlchemy models (tables) inherit from this Base
class Base(DeclarativeBase):
    pass


# Dependency — used in FastAPI route handlers to get a DB session
# Automatically closes the session when the request finishes
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
