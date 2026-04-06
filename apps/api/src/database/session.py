from collections.abc import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from src.core.config import db_settings

# Create a database engine to connect with database
engine = create_async_engine(
    # database type/dialect and file name
    url=db_settings.POSTGRES_URL,
    # Log sql queries
    # echo=True,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a session from the database
    """
    async_session = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False,
    )

    async with async_session() as session:
        yield session


async def ping_database(session: AsyncSession) -> bool:
    """
    Check whether the database is reachable.
    """
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True
