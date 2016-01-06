from asyncio import coroutine
from contextlib import closing

from sqlalchemy.engine import Connection, Engine
from sqlalchemy.engine.strategies import DefaultEngineStrategy
from sqlalchemy.ext.horizontal_shard import ShardedSession
from sqlalchemy.orm import Query, Session
from asphalt.core.concurrency import is_event_loop_thread, blocking


class AsyncConnection(Connection):
    """
    An asyncio friendly version of the :class:`~sqlalchemy.engine.Connection` class.

    The following methods have been wrapped with ``@blocking``:

    * :meth:`~sqlalchemy.engine.Connection.execute`
    * :meth:`~sqlalchemy.engine.Connection.scalar`
    * :meth:`~sqlalchemy.engine.Connection.run_callable`
    * :meth:`~sqlalchemy.engine.Connection.transaction`
    """

    execute = blocking(Connection.execute)
    run_callable = blocking(Connection.run_callable)
    scalar = blocking(Connection.scalar)
    transaction = blocking(Connection.transaction)


class AsyncEngine(Engine):
    """
    An asyncio friendly version of the :class:`~sqlalchemy.engine.Engine` class.

    The following methods have been wrapped with ``@blocking``:

    * :meth:`~sqlalchemy.engine.Engine.connect`
    * :meth:`~sqlalchemy.engine.Engine.contextual_connect`
    * :meth:`~sqlalchemy.engine.Engine.execute`
    * :meth:`~sqlalchemy.engine.Engine.run_callable`
    * :meth:`~sqlalchemy.engine.Engine.transaction`
    """

    connect = blocking(Engine.connect)
    contextual_connect = blocking(Engine.contextual_connect)
    execute = blocking(Engine.execute)
    run_callable = blocking(Engine.run_callable)
    transaction = blocking(Engine.transaction)


class AsyncQuery(Query):
    """
    An asyncio friendly version of the :class:`~sqlalchemy.orm.query.Query` class.

    The following methods have been wrapped with ``@blocking``:

    * :meth:`~sqlalchemy.orm.query.Query.all`
    * :meth:`~sqlalchemy.orm.query.Query.count`
    * :meth:`~sqlalchemy.orm.query.Query.delete`
    * :meth:`~sqlalchemy.orm.query.Query.first`
    * :meth:`~sqlalchemy.orm.query.Query.get`
    * :meth:`~sqlalchemy.orm.query.Query.one`
    * :meth:`~sqlalchemy.orm.query.Query.one_or_none`
    * :meth:`~sqlalchemy.orm.query.Query.scalar`
    * :meth:`~sqlalchemy.orm.query.Query.update`
    """

    all = blocking(Query.all)
    count = blocking(Query.count)
    delete = blocking(Query.delete)
    first = blocking(Query.first)
    get = blocking(Query.get)
    one = blocking(Query.one)
    one_or_none = blocking(Query.one_or_none)
    scalar = blocking(Query.scalar)
    update = blocking(Query.update)


class AsyncSession(Session):
    """
    An asyncio friendly version of the :class:`~sqlalchemy.orm.session.Session` class.

    This session class supports use as a regular or asynchronous context manager (``with`` or
    ``async with``). It will automatically call :meth:`commit` if the block is exited without
    having raised an exception.

    The following methods have been wrapped with ``@blocking``:

    * :meth:`~sqlalchemy.orm.session.Session.bulk_insert_mappings`
    * :meth:`~sqlalchemy.orm.session.Session.bulk_save_objects`
    * :meth:`~sqlalchemy.orm.session.Session.bulk_update_mappings`
    * :meth:`~sqlalchemy.orm.session.Session.execute`
    * :meth:`~sqlalchemy.orm.session.Session.commit`
    * :meth:`~sqlalchemy.orm.session.Session.flush`
    * :meth:`~sqlalchemy.orm.session.Session.merge`
    * :meth:`~sqlalchemy.orm.session.Session.refresh`
    * :meth:`~sqlalchemy.orm.session.Session.scalar`
    """

    def __init__(self, *args, query_cls=AsyncQuery, **kwargs):
        super().__init__(*args, query_cls=query_cls, **kwargs)

    def __enter__(self):
        if is_event_loop_thread():
            raise RuntimeError('the session may not be used as a regular context manager in the '
                               'event loop thread -- use "async with" instead')

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        with closing(self):
            if exc_type is None and self.is_active:
                self.commit()

    @coroutine
    def __aenter__(self):
        return self

    @coroutine
    def __aexit__(self, exc_type, exc_val, exc_tb):
        with closing(self):
            if exc_type is None and self.is_active:
                yield from self.commit()

    bulk_insert_mappings = blocking(Session.bulk_insert_mappings)
    bulk_save_objects = blocking(Session.bulk_save_objects)
    bulk_update_mappings = blocking(Session.bulk_update_mappings)
    execute = blocking(Session.execute)
    commit = blocking(Session.commit)
    flush = blocking(Session.flush)
    merge = blocking(Session.merge)
    refresh = blocking(Session.refresh)
    scalar = blocking(Session.scalar)


class AsyncShardedSession(ShardedSession, AsyncSession):
    """
    An asyncio friendly version of the :class:`~sqlalchemy.ext.horizontal_shard.ShardedSession`
    class that also inherits all the functionality from the :class:`AsyncSession` class.

    The following method from ShardedSession has been wrapped with ``@blocking``:

    * :meth:`~sqlalchemy.ext.horizontal_shard.ShardedSession.connection`
    """

    connection = blocking(ShardedSession.connection)


class AsyncEngineStrategy(DefaultEngineStrategy):
    name = 'async'
    engine_cls = AsyncEngine

AsyncEngineStrategy()  # needed to register the "async" strategy
