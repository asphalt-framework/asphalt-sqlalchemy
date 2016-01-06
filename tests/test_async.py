import pytest

from asphalt.core.concurrency import blocking
from asphalt.sqlalchemy.async import AsyncSession


@pytest.mark.parametrize('raise_exception', [False, True])
@pytest.mark.asyncio
@blocking
def test_session_context_manager(connection, raise_exception):
    """
    Test that the context manager commits the transaction if no exception was raised in the
    block, and rolls back if an exception was raised.

    """
    exception = Exception('dummy')
    session = None
    try:
        with AsyncSession(bind=connection) as session:
            session.execute('INSERT INTO foo (id) VALUES(3)')
            if raise_exception:
                raise exception
    except Exception as e:
        if e is not exception:
            raise

    rows = session.execute('SELECT * FROM foo').fetchall()
    assert len(rows) == (0 if raise_exception else 1)


def test_session_context_manager_wrong_thread():
    """
    Test that the context manager refuses to let the regular context manager to be used from the
    event loop thread.

    """
    with pytest.raises(RuntimeError) as exc, AsyncSession():
        pass

    assert str(exc.value) == ('the session may not be used as a regular context manager in the '
                              'event loop thread -- use "async with" instead')


@pytest.mark.parametrize('raise_exception', [False, True])
@pytest.mark.asyncio
def test_session_async_context_manager(connection, raise_exception):
    """
    Test that the async context manager commits the transaction if no exception was raised in the
    block, and rolls back if an exception was raised.

    """
    session = AsyncSession(bind=connection)
    retval = yield from session.__aenter__()
    assert retval is session

    yield from session.execute('INSERT INTO foo (id) VALUES(3)')
    exc_type, exc_value = (Exception, Exception('dummy')) if raise_exception else (None, None)
    yield from session.__aexit__(exc_type, exc_value, None)

    rows = (yield from session.execute('SELECT * FROM foo')).fetchall()
    assert len(rows) == (0 if raise_exception else 1)
