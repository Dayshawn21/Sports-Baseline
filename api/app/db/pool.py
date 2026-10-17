from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings

engine = create_async_engine(
    settings.async_database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
