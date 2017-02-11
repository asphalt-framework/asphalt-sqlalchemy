import gc
from concurrent.futures import Executor, ThreadPoolExecutor
from contextlib import closing
from weakref import ProxyType

import pytest
from asphalt.core.context import Context, ResourceNotFound
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm.session import sessionmaker, Session
from sqlalchemy.sql.schema import MetaData

from asphalt.sqlalchemy.component import SQLAlchemyComponent
from asphalt.sqlalchemy.util import connect_test_database


@pytest.fixture
def connection():
    with closing(connect_test_database('sqlite:///')) as connection:
        connection.execute('CREATE TABLE foo (id INTEGER PRIMARY KEY)')
        yield connection


@pytest.fixture
def executor():
    pool = ThreadPoolExecutor(1)
    yield pool
    pool.shutdown()


@pytest.mark.parametrize('session', [True, False])
@pytest.mark.asyncio
async def test_component_start(session):
    metadata = MetaData()
    component = SQLAlchemyComponent(url='sqlite://', metadata=metadata, session=session)
    ctx = Context()
    await component.start(ctx)

    engine = await ctx.request_resource(Engine)
    assert ctx.sql is engine
    assert metadata.bind is engine

    if session:
        maker = await ctx.request_resource(sessionmaker, timeout=0)
        assert isinstance(maker, sessionmaker)
        assert isinstance(ctx.dbsession, Session)
        assert ctx.dbsession.bind is ctx.sql
    else:
        with pytest.raises(ResourceNotFound):
            await ctx.request_resource(sessionmaker, timeout=0)

        assert not hasattr(ctx, 'dbsession')


@pytest.mark.asyncio
async def test_multiple_engines():
    component = SQLAlchemyComponent(engines={'db1': {}, 'db2': {}}, url='sqlite://')
    ctx = Context()
    await component.start(ctx)

    assert isinstance(ctx.db1, Engine)
    assert isinstance(ctx.db2, Engine)
    assert ctx.dbsession.bind is None


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
    session = dict(commit_executor=executor if commit_executor == 'instance' else commit_executor)
    component = SQLAlchemyComponent(url={'drivername': 'sqlite', 'database': str(db_path)},
                                    session=session)
    ctx = Context()
    ctx.publish_resource(executor, types=[Executor])
    await component.start(ctx)
    ctx.dbsession.execute('CREATE TABLE foo (id INTEGER PRIMARY KEY)')
    ctx.dbsession.execute('INSERT INTO foo (id) VALUES(3)')
    await ctx.finished.dispatch(Exception('dummy') if raise_exception else None,
                                return_future=True)

    rows = ctx.sql.execute('SELECT * FROM foo').fetchall()
    assert len(rows) == (0 if raise_exception else 1)


def test_missing_url_bind():
    exc = pytest.raises(ValueError, SQLAlchemyComponent)
    assert str(exc.value) == 'specify either url or bind'


@pytest.mark.asyncio
async def test_memory_leak():
    """Test that creating a session in a context does not leak memory."""
    component = SQLAlchemyComponent(url='sqlite:///:memory:')
    async with Context() as ctx:
        await component.start(ctx)
        assert isinstance(ctx.dbsession, Session)

    del ctx
    gc.collect()  # needed on PyPy
    assert next((x for x in gc.get_objects() if not isinstance(x, ProxyType) and
                 isinstance(x, Context)), None) is None
