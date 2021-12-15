import gc
from concurrent.futures import Executor, ThreadPoolExecutor

import pytest
from asphalt.core.context import Context
from sqlalchemy import create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm.session import Session, sessionmaker
from sqlalchemy.pool import NullPool

from asphalt.sqlalchemy.component import SQLAlchemyComponent


@pytest.fixture
def executor():
    pool = ThreadPoolExecutor(1)
    yield pool
    pool.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize('poolclass', [None, 'sqlalchemy.pool:StaticPool'])
async def test_component_start(poolclass):
    """Test that the component creates all the expected resources."""
    url = URL.create('sqlite', database=':memory:')
    component = SQLAlchemyComponent(url=url, poolclass=poolclass)
    async with Context() as ctx:
        await component.start(ctx)

        engine = ctx.require_resource(Engine)
        ctx.require_resource(sessionmaker)
        assert ctx.sql is ctx.require_resource(Session)
        assert ctx.sql.bind is engine


@pytest.mark.asyncio
async def test_multiple_engines():
    component = SQLAlchemyComponent(engines={'db1': {}, 'db2': {}}, url='sqlite:///:memory:')
    async with Context() as ctx:
        await component.start(ctx)

        engine1 = ctx.require_resource(Engine, 'db1')
        engine2 = ctx.require_resource(Engine, 'db2')
        assert ctx.db1.bind is engine1
        assert ctx.db2.bind is engine2


@pytest.mark.parametrize('asynchronous', [False, True], ids=['sync', 'async'])
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
    component = SQLAlchemyComponent(url='sqlite:///:memory:', ready_callback=callback)
    async with Context() as ctx:
        await component.start(ctx)

        engine = ctx.require_resource(Engine)
        factory = ctx.require_resource(sessionmaker)
        assert engine is engine2
        assert factory is factory2


@pytest.mark.asyncio
async def test_bind():
    """Test that a Connection can be passed as "bind" in place of "url"."""
    engine = create_engine('sqlite:///:memory:')
    connection = engine.connect()
    component = SQLAlchemyComponent(bind=connection)
    async with Context() as ctx:
        await component.start(ctx)

        assert ctx.require_resource(Engine) is engine
        assert ctx.sql.bind is connection


def test_no_url_or_bind():
    exc = pytest.raises(TypeError, SQLAlchemyComponent)
    exc.match('both "url" and "bind" cannot be None')


@pytest.mark.parametrize('raise_exception', [False, True])
@pytest.mark.parametrize('commit_executor', [None, 'default', 'instance'],
                         ids=['none', 'default', 'instance'])
@pytest.mark.asyncio
async def test_finish_commit(raise_exception, executor, commit_executor, tmpdir):
    """
    Tests that the session is automatically committed if and only if the context was not exited
    with an exception.

    """
    db_path = tmpdir.join('test.db')
    engine = create_engine('sqlite:///%s' % db_path, poolclass=NullPool)
    engine.execute('CREATE TABLE foo (id INTEGER PRIMARY KEY)')

    component = SQLAlchemyComponent(
        url={'drivername': 'sqlite', 'database': str(db_path)},
        commit_executor=executor if commit_executor == 'instance' else commit_executor)
    ctx = Context()
    ctx.add_resource(executor, types=[Executor])
    await component.start(ctx)
    ctx.sql.execute('INSERT INTO foo (id) VALUES(3)')
    await ctx.close(Exception('dummy') if raise_exception else None)

    rows = engine.execute('SELECT * FROM foo').fetchall()
    assert len(rows) == (0 if raise_exception else 1)


@pytest.mark.asyncio
async def test_memory_leak():
    """Test that creating a session in a context does not leak memory."""
    component = SQLAlchemyComponent(url='sqlite:///:memory:')
    async with Context() as ctx:
        await component.start(ctx)
        assert isinstance(ctx.sql, Session)

    del ctx
    gc.collect()  # needed on PyPy
    assert next((x for x in gc.get_objects() if isinstance(x, Context)), None) is None
