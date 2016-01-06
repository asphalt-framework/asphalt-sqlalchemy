from sqlalchemy.engine.base import Engine
from sqlalchemy.orm.session import sessionmaker, Session
from sqlalchemy.sql.schema import MetaData
from asphalt.core.context import Context, ResourceNotFound
import pytest

from asphalt.sqlalchemy.component import SQLAlchemyComponent


@pytest.mark.parametrize('session', [True, False])
@pytest.mark.asyncio
def test_component_start(session):
    metadata = MetaData()
    component = SQLAlchemyComponent(url='sqlite://', metadata=metadata, session=session)
    ctx = Context()
    yield from component.start(ctx)

    engine = yield from ctx.request_resource(Engine)
    assert ctx.sql is engine
    assert metadata.bind is engine

    if session:
        maker = yield from ctx.request_resource(sessionmaker, timeout=0)
        assert isinstance(maker, sessionmaker)
        assert isinstance(ctx.dbsession, Session)
        assert ctx.dbsession.bind is ctx.sql
    else:
        with pytest.raises(ResourceNotFound):
            yield from ctx.request_resource(sessionmaker, timeout=0)
        assert not hasattr(ctx, 'dbsession')


@pytest.mark.asyncio
def test_multiple_engines():
    component = SQLAlchemyComponent(engines={
        'db1': {'url': 'sqlite://'},
        'db2': {'url': 'sqlite://'}
    })
    ctx = Context()
    yield from component.start(ctx)

    assert isinstance(ctx.db1, Engine)
    assert isinstance(ctx.db2, Engine)
    assert ctx.dbsession.bind is None


@pytest.mark.parametrize('raise_exception', [False, True])
@pytest.mark.asyncio
def test_finish_commit(raise_exception, tmpdir):
    """
    Tests that the session is automatically committed if and only if the context was not exited
    with an exception.

    """
    db_path = tmpdir.join('test.db')
    component = SQLAlchemyComponent(url='sqlite:///%s' % db_path)
    ctx = Context()
    yield from component.start(ctx)
    yield from ctx.dbsession.execute('CREATE TABLE foo (id INTEGER PRIMARY KEY)')
    yield from ctx.dbsession.execute('INSERT INTO foo (id) VALUES(3)')
    yield from ctx.dispatch('finished', Exception('dummy') if raise_exception else None)

    rows = (yield from ctx.sql.execute('SELECT * FROM foo')).fetchall()
    assert len(rows) == (0 if raise_exception else 1)


def test_conflicting_config():
    exc = pytest.raises(ValueError, SQLAlchemyComponent, engines={'default': {}}, url='sqlite://')
    assert str(exc.value) == ('specify either an "engines" dictionary or the default engine\'s '
                              'options directly, but not both')


def test_missing_url_bind():
    exc = pytest.raises(ValueError, SQLAlchemyComponent)
    assert str(exc.value) == 'specify either url or bind'
