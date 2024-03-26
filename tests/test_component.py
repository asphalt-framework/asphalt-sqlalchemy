from __future__ import annotations

import gc
from contextlib import AsyncExitStack
from pathlib import Path
from threading import Thread, current_thread
from typing import Any

import pytest
from asphalt.core import (
    Context,
    NoCurrentContext,
    current_context,
    get_resource_nowait,
)
from pytest import FixtureRequest
from sqlalchemy.engine.url import URL
from sqlalchemy.event import listen, remove
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.future import Engine, create_engine
from sqlalchemy.orm.session import Session, sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool, QueuePool
from sqlalchemy.sql import text

from asphalt.sqlalchemy import SQLAlchemyComponent, clear_async_database, clear_database

from .model import Person

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    "component_opts, args",
    [
        pytest.param({}, ()),
        pytest.param({"resource_name": "alternate"}, ("alternate",)),
    ],
)
async def test_component_start_sync(
    component_opts: dict[str, Any], args: tuple[Any]
) -> None:
    """Test that the component creates all the expected (synchronous) resources."""
    url = URL.create("sqlite", database=":memory:")
    component = SQLAlchemyComponent(url=url, **component_opts)
    async with Context():
        await component.start()

        get_resource_nowait(Engine, *args)
        get_resource_nowait(sessionmaker, *args)
        get_resource_nowait(Session, *args)


@pytest.mark.parametrize(
    "component_opts, args",
    [
        pytest.param({}, ()),
        pytest.param({"resource_name": "alternate"}, ("alternate",)),
    ],
)
async def test_component_start_async(
    component_opts: dict[str, Any], args: tuple[Any]
) -> None:
    """Test that the component creates all the expected (asynchronous) resources."""
    url = URL.create("sqlite+aiosqlite", database=":memory:")
    component = SQLAlchemyComponent(url=url, **component_opts)
    async with Context():
        await component.start()

        get_resource_nowait(AsyncEngine, *args)
        async_session_class = get_resource_nowait(async_sessionmaker, *args)
        get_resource_nowait(AsyncSession, *args)
        sync_session_class = get_resource_nowait(sessionmaker, *args)
        assert async_session_class.kw["sync_session_class"] is sync_session_class


@pytest.mark.parametrize(
    "asynchronous", [pytest.param(False, id="sync"), pytest.param(True, id="async")]
)
async def test_ready_callback(asynchronous: bool) -> None:
    engine2: Engine | AsyncEngine | None = None
    factory2: sessionmaker[Any] | async_sessionmaker[Any] | None = None

    def ready_callback(engine: Engine, factory: sessionmaker[Any]) -> None:
        nonlocal engine2, factory2
        engine2 = engine
        factory2 = factory

    async def ready_callback_async(
        engine: AsyncEngine, factory: async_sessionmaker[Any]
    ) -> None:
        nonlocal engine2, factory2
        engine2 = engine
        factory2 = factory

    callback = ready_callback_async if asynchronous else ready_callback
    component = SQLAlchemyComponent(url="sqlite:///:memory:", ready_callback=callback)
    async with Context():
        await component.start()

        engine = get_resource_nowait(Engine)
        factory = get_resource_nowait(sessionmaker)
        assert engine is engine2
        assert factory is factory2


async def test_bind_sync_connection() -> None:
    """Test that a Connection can be passed as "bind" in place of "url"."""
    engine = create_engine("sqlite:///:memory:")
    connection = engine.connect()
    component = SQLAlchemyComponent(bind=connection)
    async with Context():
        await component.start()

        assert get_resource_nowait(Engine) is engine
        assert get_resource_nowait(Session).bind is connection

    connection.close()


async def test_bind_async_connection(aiosqlite_memory_url: str) -> None:
    """Test that a Connection can be passed as "bind" in place of "url"."""
    engine = create_async_engine(aiosqlite_memory_url)
    connection = await engine.connect()
    component = SQLAlchemyComponent(bind=connection)
    async with Context():
        await component.start()

        assert get_resource_nowait(AsyncEngine) is engine
        assert get_resource_nowait(AsyncSession).bind is connection

    await connection.close()


async def test_bind_sync_engine() -> None:
    """Test that a Connection can be passed as "bind" in place of "url"."""
    engine = create_engine("sqlite:///:memory:")
    component = SQLAlchemyComponent(bind=engine)
    async with Context():
        await component.start()

        assert get_resource_nowait(Engine) is engine
        assert get_resource_nowait(Session).bind is engine

    engine.dispose()


async def test_bind_async_engine() -> None:
    """Test that a Connection can be passed as "bind" in place of "url"."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    component = SQLAlchemyComponent(bind=engine)
    async with Context():
        await component.start()

        assert get_resource_nowait(AsyncEngine) is engine
        assert get_resource_nowait(AsyncSession).bind is engine

    await engine.dispose()


async def test_close_twice_sync(psycopg_url: str) -> None:
    """Test that closing a session releases connection resources, but remains usable."""
    component = SQLAlchemyComponent(url=psycopg_url, prefer_async=False)
    async with Context():
        await component.start()
        session = get_resource_nowait(Session)
        assert isinstance(session.bind, Engine)
        pool = session.bind.pool
        assert isinstance(pool, QueuePool)
        session.execute(text("SELECT 1"))
        assert pool.checkedout() == 1
        session.close()
        assert pool.checkedout() == 0
        session.execute(text("SELECT 1"))
        assert pool.checkedout() == 1

    assert pool.checkedout() == 0


async def test_close_twice_async(psycopg_url_async: str) -> None:
    """Test that closing a session releases connection resources, but remains usable."""
    component = SQLAlchemyComponent(url=psycopg_url_async)
    async with Context():
        await component.start()
        session = get_resource_nowait(AsyncSession)
        assert isinstance(session.bind, AsyncEngine)
        pool = session.bind.pool
        assert isinstance(pool, AsyncAdaptedQueuePool)
        await session.execute(text("SELECT 1"))
        assert pool.checkedout() == 1
        await session.close()
        assert pool.checkedout() == 0
        await session.execute(text("SELECT 1"))
        assert pool.checkedout() == 1

    assert pool.checkedout() == 0


def test_no_url_or_bind() -> None:
    exc = pytest.raises(TypeError, SQLAlchemyComponent)
    exc.match('both "url" and "bind" cannot be None')


@pytest.mark.parametrize("raise_exception", [False, True])
async def test_finish_commit(raise_exception: bool, tmp_path: Path) -> None:
    """
    Tests that the session is automatically committed if and only if the context was not
    exited with an exception.

    """
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", poolclass=NullPool)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE foo (id INTEGER PRIMARY KEY)"))

        component = SQLAlchemyComponent(
            url={"drivername": "sqlite", "database": str(db_path)},
        )
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(Context())
            await component.start()
            session = get_resource_nowait(Session)
            session.execute(text("INSERT INTO foo (id) VALUES(3)"))
            if raise_exception:
                stack.enter_context(pytest.raises(Exception, match="dummy"))
                raise Exception("dummy")

        rows = connection.execute(text("SELECT * FROM foo")).fetchall()
        assert len(rows) == (0 if raise_exception else 1)


async def test_memory_leak() -> None:
    """Test that creating a session in a context does not leak memory."""
    component = SQLAlchemyComponent(url="sqlite:///:memory:")
    async with Context():
        await component.start()
        get_resource_nowait(Session)

    gc.collect()  # needed on PyPy
    assert next((x for x in gc.get_objects() if isinstance(x, Context)), None) is None


async def test_session_event_sync(psycopg_url_async: str) -> None:
    """Test that creating a session in a context does not leak memory."""
    listener_session: Session | None = None
    listener_thread: Thread | None = None

    def listener(session: Session) -> None:
        nonlocal listener_session, listener_thread
        current_context()
        listener_session = session
        listener_thread = current_thread()

    component = SQLAlchemyComponent(url=psycopg_url_async, prefer_async=False)
    engine: Engine
    try:
        async with Context():
            await component.start()
            engine = get_resource_nowait(Engine)
            Person.metadata.create_all(engine)
            session_factory = get_resource_nowait(sessionmaker)
            listen(session_factory, "before_commit", listener)

            dbsession = get_resource_nowait(Session)
            dbsession.add(Person(name="Test person"))

        assert listener_session is dbsession
        assert listener_thread != current_thread()
    finally:
        with engine.connect() as conn:
            clear_database(conn)


async def test_session_event_async(
    request: FixtureRequest, psycopg_url_async: str
) -> None:
    """Test that creating a session in a context does not leak memory."""
    listener_session: Session | None = None
    listener_thread: Thread | None = None

    def listener(session: Session) -> None:
        nonlocal listener_session, listener_thread
        try:
            async_session = get_resource_nowait(AsyncSession)
        except NoCurrentContext:
            return

        if async_session and session is async_session.sync_session:
            listener_session = session
            listener_thread = current_thread()

    listen(Session, "before_commit", listener)
    request.addfinalizer(lambda: remove(Session, "before_commit", listener))
    component = SQLAlchemyComponent(url=psycopg_url_async)
    engine: AsyncEngine | None = None
    try:
        async with Context():
            await component.start()
            engine = get_resource_nowait(AsyncEngine)
            dbsession = get_resource_nowait(AsyncSession)
            await dbsession.run_sync(
                lambda session: Person.metadata.create_all(
                    session.bind  # type: ignore[arg-type]
                )
            )
            dbsession.add(Person(name="Test person"))

        assert listener_session is dbsession.sync_session
        assert listener_thread is current_thread()
    finally:
        if engine:
            async with engine.connect() as conn:
                await clear_async_database(conn)
                await conn.commit()

    assert listener_session is dbsession.sync_session
    assert listener_thread is current_thread()
