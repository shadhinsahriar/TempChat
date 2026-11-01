"""Pytest configuration, async database fixtures, and test client."""

import asyncio
import shutil
import tempfile
from collections.abc import AsyncGenerator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app as fastapi_app
from app.services.storage.local import LocalStorageProvider
from app.services.storage_service import default_storage_service

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# Relax rate limits for automated tests
settings.RATE_LIMIT_CREATE_ROOM = 100000
settings.RATE_LIMIT_JOIN_ROOM = 100000
settings.RATE_LIMIT_MESSAGES = 100000
settings.RATE_LIMIT_UPLOADS = 100000


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
        future=True,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    import app.db.session

    original_engine = app.db.session.engine
    original_factory = app.db.session.async_session_factory

    test_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    app.db.session.engine = engine
    app.db.session.async_session_factory = test_factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    app.db.session.engine = original_engine
    app.db.session.async_session_factory = original_factory
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    import app.db.session

    async with app.db.session.async_session_factory() as session:
        yield session


@pytest.fixture(scope="function")
def isolated_storage():
    temp_dir = tempfile.mkdtemp()
    original_provider = default_storage_service.provider
    default_storage_service.provider = LocalStorageProvider(base_dir=temp_dir)
    yield temp_dir
    default_storage_service.provider = original_provider
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
async def client(
    db_engine: AsyncEngine, isolated_storage
) -> AsyncGenerator[httpx.AsyncClient, None]:
    import app.db.session

    async def override_get_db():
        async with app.db.session.async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    fastapi_app.dependency_overrides[get_db_session] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()
