import gc
from concurrent.futures import Executor, ThreadPoolExecutor

import pytest
from asphalt.core.context import Context
from sqlalchemy import create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm.session import sessionmaker, Session
from sqlalchemy.pool import NullPool

from asphalt.sqlalchemy.component import SQLAlchemyComponent


@pytest.fixture
def connection():
    engine = create_engine('sqlite:///:memory:')
    connection = engine.connect()
    connection.execute('CREATE TABLE foo (id INTEGER PRIMARY KEY)')
    yield connection
    connection.close()
    engine.dispose()


@pytest.fixture
def executor():
    pool = ThreadPoolExecutor(1)
    yield pool
    pool.shutdown()


@pytest.mark.asyncio
async def test_component_start():
    """Test that the component creates all the expected resources."""
    component = SQLAlchemyComponent(url='sqlite:///:memory:')
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
