import logging
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

logger = logging.getLogger(__name__)

# Normalize DATABASE_URL for async drivers
database_url = settings.DATABASE_URL
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif database_url.startswith("sqlite:///") and not database_url.startswith("sqlite+aiosqlite:///"):
    database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

# SQLite specific connect args for async support
connect_args = {}
if "sqlite" in database_url:
    connect_args["check_same_thread"] = False

engine = create_async_engine(
    database_url,
    echo=settings.DATABASE_ECHO,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Optional Redis client with resilient in-memory fallback
class CacheService:
    def __init__(self):
        self._redis = None
        self._memory_cache = {}

    async def init(self):
        if settings.REDIS_ENABLED and settings.REDIS_URL:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                await self._redis.ping()
                logger.info("Connected to Redis cache.")
            except Exception as e:
                logger.warning(f"Redis unavailable, falling back to memory cache: {e}")
                self._redis = None

    async def get(self, key: str) -> Optional[str]:
        if self._redis:
            try:
                return await self._redis.get(key)
            except Exception:
                pass
        return self._memory_cache.get(key)

    async def set(self, key: str, value: str, expire_seconds: int = 3600) -> bool:
        if self._redis:
            try:
                await self._redis.set(key, value, ex=expire_seconds)
                return True
            except Exception:
                pass
        self._memory_cache[key] = value
        return True

    async def delete(self, key: str) -> bool:
        if self._redis:
            try:
                await self._redis.delete(key)
                return True
            except Exception:
                pass
        self._memory_cache.pop(key, None)
        return True

    async def close(self):
        if self._redis:
            await self._redis.close()


cache = CacheService()

