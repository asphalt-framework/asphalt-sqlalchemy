import gc
from contextlib import ExitStack
from threading import Thread, current_thread

import pytest
from asphalt.core import NoCurrentContext, current_context
from asphalt.core.context import Context, get_resource
from sqlalchemy.engine.url import URL
from sqlalchemy.event import listen, remove
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.future import Engine, create_engine
from sqlalchemy.orm.session import Session, sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import text

from asphalt.sqlalchemy.component import SQLAlchemyComponent

from .model import Person


@pytest.mark.asyncio
async def test_component_start_sync():
    """Test that the component creates all the expected (synchronous) resources."""
    url = URL.create("sqlite", database=":memory:")
    component = SQLAlchemyComponent(url=url)
    async with Context() as ctx:
        await component.start(ctx)

        ctx.require_resource(Engine)
        ctx.require_resource(sessionmaker)
        ctx.require_resource(Session)


@pytest.mark.asyncio
async def test_component_start_async():
    """Test that the component creates all the expected (asynchronous) resources."""
    url = URL.create("sqlite+aiosqlite", database=":memory:")
    component = SQLAlchemyComponent(url=url)
    async with Context() as ctx:
        await component.start(ctx)

        ctx.require_resource(AsyncEngine)
        ctx.require_resource(sessionmaker)
        ctx.require_resource(AsyncSession)


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.asyncio
async def test_ready_callback(asynchronous):
    def ready_callback(engine, factory):
        nonlocal engine2, factory2
        engine2 = engine
        factory2 = factory

    async def ready_callback_async(engine, factory):
        nonlocal engine2, factory2
        engine2 = engine
        factory2 = factory

    engine2 = factory2 = None
    callback = ready_callback_async if asynchronous else ready_callback
    component = SQLAlchemyComponent(url="sqlite:///:memory:", ready_callback=callback)
    async with Context() as ctx:
        await component.start(ctx)

        engine = ctx.require_resource(Engine)
        factory = ctx.require_resource(sessionmaker)
        assert engine is engine2
        assert factory is factory2


@pytest.mark.asyncio
async def test_bind_sync():
    """Test that a Connection can be passed as "bind" in place of "url"."""
    engine = create_engine("sqlite:///:memory:")
    connection = engine.connect()
    component = SQLAlchemyComponent(bind=connection)
    async with Context() as ctx:
        await component.start(ctx)

        assert ctx.require_resource(Engine) is engine
        assert ctx.require_resource(Session).bind is connection

    connection.close()


@pytest.mark.asyncio
async def test_bind_async():
    """Test that a Connection can be passed as "bind" in place of "url"."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    connection = await engine.connect()
    component = SQLAlchemyComponent(bind=connection)
    async with Context() as ctx:
        await component.start(ctx)

        assert ctx.require_resource(AsyncEngine) is engine
        assert ctx.require_resource(AsyncSession).bind is connection

    await connection.close()


@pytest.mark.asyncio
async def test_close_twice_sync(patch_psycopg2, psycopg2_url):
    """Test that closing a session releases connection resources, but remains usable."""
    component = SQLAlchemyComponent(url=psycopg2_url)
    async with Context() as ctx:
        await component.start(ctx)
        session = ctx.require_resource(Session)
        pool = session.bind.pool
        session.execute(text("SELECT 1"))
        assert pool.checkedout() == 1
        session.close()
        assert pool.checkedout() == 0
        session.execute(text("SELECT 1"))
        assert pool.checkedout() == 1

    assert pool.checkedout() == 0


@pytest.mark.asyncio
async def test_close_twice_async(asyncpg_url):
    """Test that closing a session releases connection resources, but remains usable."""
    component = SQLAlchemyComponent(url=asyncpg_url)
    async with Context() as ctx:
        await component.start(ctx)
        session = ctx.require_resource(AsyncSession)
        pool = session.bind.pool
        await session.execute(text("SELECT 1"))
        assert pool.checkedout() == 1
        await session.close()
        assert pool.checkedout() == 0
        await session.execute(text("SELECT 1"))
        assert pool.checkedout() == 1

    assert pool.checkedout() == 0


def test_no_url_or_bind():
    exc = pytest.raises(TypeError, SQLAlchemyComponent)
    exc.match('both "url" and "bind" cannot be None')


@pytest.mark.parametrize("raise_exception", [False, True])
@pytest.mark.asyncio
async def test_finish_commit(raise_exception, tmp_path):
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
        with ExitStack() as stack:
            async with Context() as ctx:
                await component.start(ctx)
                session = ctx.require_resource(Session)
                session.execute(text("INSERT INTO foo (id) VALUES(3)"))
                if raise_exception:
                    stack.enter_context(pytest.raises(Exception, match="dummy"))
                    raise Exception("dummy")

        rows = connection.execute(text("SELECT * FROM foo")).fetchall()
        assert len(rows) == (0 if raise_exception else 1)


@pytest.mark.asyncio
async def test_memory_leak():
    """Test that creating a session in a context does not leak memory."""
    component = SQLAlchemyComponent(url="sqlite:///:memory:")
    async with Context() as ctx:
        await component.start(ctx)
        ctx.require_resource(Session)

    del ctx
    gc.collect()  # needed on PyPy
    assert next((x for x in gc.get_objects() if isinstance(x, Context)), None) is None


@pytest.mark.asyncio
async def test_session_event_sync(psycopg2_url):
    """Test that creating a session in a context does not leak memory."""
    listener_session: Session
    listener_thread: Thread

    def listener(session: Session) -> None:
        nonlocal listener_session, listener_thread
        current_context()
        listener_session = session
        listener_thread = current_thread()

    component = SQLAlchemyComponent(url=psycopg2_url)
    async with Context() as ctx:
        await component.start(ctx)
        Person.metadata.create_all(ctx.require_resource(Engine))
        session_factory = ctx.require_resource(sessionmaker)
        listen(session_factory, "before_commit", listener)

        dbsession = ctx.require_resource(Session)
        dbsession.add(Person(name="Test person"))

    assert listener_session is dbsession
    assert listener_thread != current_thread()


@pytest.mark.asyncio
async def test_session_event_async(request, asyncpg_url, psycopg2_url):
    """Test that creating a session in a context does not leak memory."""
    listener_session: Session
    listener_thread: Thread

    def listener(session: Session) -> None:
        nonlocal listener_session, listener_thread
        try:
            async_session = get_resource(AsyncSession)
        except NoCurrentContext:
            return

        if async_session and session is async_session.sync_session:
            listener_session = session
            listener_thread = current_thread()

    listen(Session, "before_commit", listener)
    request.addfinalizer(lambda: remove(Session, "before_commit", listener))
    component = SQLAlchemyComponent(url=asyncpg_url)
    async with Context() as ctx:
        await component.start(ctx)
        dbsession = ctx.require_resource(AsyncSession)
        await dbsession.run_sync(
            lambda session: Person.metadata.create_all(session.bind)
        )
        dbsession.add(Person(name="Test person"))

    assert listener_session is dbsession.sync_session
    assert listener_thread is current_thread()

    engine = create_engine(psycopg2_url)
    with Session(engine) as sess:
        sess.add(Person(name="Test person 2"))
        sess.commit()

    engine.dispose()

    assert listener_session is dbsession.sync_session
    assert listener_thread is current_thread()
