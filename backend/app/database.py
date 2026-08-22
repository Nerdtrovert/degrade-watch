"""
Database connection and session management for DegradeWatch backend.
Provides both synchronous (for Alembic migrations) and asynchronous (for application) engines.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeAsyncSessionMaker, DeclarativeBase
from .config import db_config

# Synchronous engine for Alembic migrations and any synchronous operations
sync_engine = create_engine(
    db_config.url,
    echo=False,  # Set to True for debugging
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Asynchronous engine for the application
# Convert the synchronous URL to asynchronous by changing the driver
# Assuming the URL is postgresql://... we change to postgresql+asyncpg://
async_database_url = db_config.url.replace("postgresql://", "postgresql+asyncpg://")
async_engine = create_async_engine(
    async_database_url,
    echo=False,  # Set to True for debugging
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Synchronous session factory for Alembic and synchronous operations
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

# Asynchronous session factory for the application
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for declarative models
class Base(DeclarativeBase):
    pass

def get_sync_db():
    """
    Dependency to get synchronous DB session (for Alembic and synchronous operations).
    """
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_async_db():
    """
    Dependency to get asynchronous DB session (for application).
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

def create_tables():
    """
    Create all tables in the database using the synchronous engine (for Alembic compatibility).
    """
    Base.metadata.create_all(bind=sync_engine)