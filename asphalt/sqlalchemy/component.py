import logging
from concurrent.futures import Executor
from concurrent.futures.thread import ThreadPoolExecutor
from functools import partial
from typing import Dict, Any, Union, Optional

from async_generator import yield_
from asyncio_extras.threads import call_in_executor
from sqlalchemy.engine import create_engine, Engine, Connection
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.orm import sessionmaker, Session
from typeguard import check_argument_types

from asphalt.core import Component, Context, merge_config, context_teardown

logger = logging.getLogger(__name__)


class SQLAlchemyComponent(Component):
    """
    Creates resources necessary for accessing relational databases using SQLAlchemy.

    This component will create the following resources:
    
    * one :class:`~sqlalchemy.engine.Connection` resource factory for each engine
    * one :class:`~sqlalchemy.engine.Engine` resource for each engine
    * one :class:`~sqlalchemy.orm.session.Session` resource factory
    * one :class:`~sqlalchemy.orm.session.sessionmaker` resource

    If exactly one engine has been specified, the session will use the corresponding connection
    resource it for its database operations if no metadata has been specified.

    Additionally, the :class:`~sqlalchemy.orm.session.sessionmaker` will be added to the context
    as a resource to facilitate listening to session events on all created sessions.

    Context attributes for connections and the session can be set with the ``context_attr`` option,
    which is removed from the configuration before further processing.
    By default, the session is available as ``ctx.dbsession``. If ``engines`` is not defined,
    the default connection can be accessed as ``ctx.sql``. Otherwise, each connection will use the
    resource name as the context attribute by default.

    .. note:: The ``expire_on_commit`` option in sessions is hard coded to ``False``.

    :param engines: a dictionary of resource name ⭢ keyword arguments passed to
        :meth:`configure_engine`
    :param session: keyword arguments passed to :class:`~sqlalchemy.orm.session.sessionmaker`
    :param commit_executor: an :class:`~concurrent.futures.Executor` or the resource name of one
        (if not specified, a :class:`~concurrent.futures.ThreadPoolExecutor` with 5 workers is
        created)
    :param default_engine_args: default values for :meth:`configure_engine`
    """

    def __init__(self, engines: Dict[str, Dict[str, Any]] = None, session: Dict[str, Any] = None,
                 commit_executor: Union[Executor, str] = None, **default_engine_args):
        assert check_argument_types()
        if not engines:
            default_engine_args.setdefault('context_attr', 'sql')
            engines = {'default': default_engine_args}

        self.engines = []
        for resource_name, config in engines.items():
            config = merge_config(default_engine_args, config)
            context_attr = config.pop('context_attr', resource_name)
            engine = self.configure_engine(**config)
            self.engines.append((resource_name, context_attr, engine))

        session = session or {}
        session.setdefault('expire_on_commit', False)
        self.session_connection = self.engines[0][0] if len(self.engines) == 1 else None
        self.session_context_attr = session.pop('context_attr', 'dbsession')
        self.sessionmaker = sessionmaker(**session)
        self.commit_executor = commit_executor

    @classmethod
    def configure_engine(cls, url: Union[str, URL, Dict[str, Any]], **engine_args):
        """
        Create an engine and selectively apply certain hacks to make it Asphalt friendly.

        :param url: the connection url passed to :func:`~sqlalchemy.create_engine`
            (can also be a dictionary of :class:`~sqlalchemy.engine.url.URL` keyword arguments)
        :param engine_args: keyword arguments passed to :func:`~sqlalchemy.create_engine`

        """
        assert check_argument_types()
        if isinstance(url, dict):
            url = URL(**url)
        elif isinstance(url, str):
            url = make_url(url)

        # This is a hack to get SQLite to play nice with asphalt-sqlalchemy's juggling of
        # connections between multiple threads. The same connection should, however, never be
        # used in multiple threads at once.
        if url.get_dialect().name == 'sqlite':
            connect_args = engine_args.setdefault('connect_args', {})
            connect_args.setdefault('check_same_thread', False)

        return create_engine(url, **engine_args)

    def create_connection(self, ctx: Context, engine: Engine) -> Connection:
        async def teardown_connection(exception: Optional[BaseException]) -> None:
            try:
                if exception is None:
                    await call_in_executor(transaction.commit, executor=self.commit_executor)
            finally:
                del connection.info['ctx']
                connection.close()

        connection = engine.connect()
        connection.info['ctx'] = ctx
        transaction = connection.begin()
        ctx.add_teardown_callback(teardown_connection, pass_exception=True)
        return connection

    def create_session(self, ctx: Context) -> Session:
        async def teardown_session(exception: Optional[BaseException]) -> None:
            try:
                if exception is None and session.is_active:
                    await call_in_executor(session.commit, executor=self.commit_executor)
            finally:
                del session.info['ctx']
                session.close()

        connection = None
        if self.session_connection:
            connection = ctx.require_resource(Connection, self.session_connection)

        session = self.sessionmaker(bind=connection, info={'ctx': ctx})
        ctx.add_teardown_callback(teardown_session, pass_exception=True)
        return session

    @context_teardown
    async def start(self, ctx: Context):
        if isinstance(self.commit_executor, str):
            self.commit_executor = await ctx.request_resource(Executor, self.commit_executor)
        elif self.commit_executor is None:
            self.commit_executor = ThreadPoolExecutor(5)
            ctx.add_teardown_callback(self.commit_executor.shutdown)

        for resource_name, context_attr, engine in self.engines:
            ctx.add_resource(engine, resource_name)
            ctx.add_resource_factory(
                partial(self.create_connection, engine=engine), [Connection], resource_name,
                context_attr)
            logger.info('Configured SQLAlchemy engine (%s / ctx.%s; dialect=%s)', resource_name,
                        context_attr, engine.dialect.name)

        ctx.add_resource(self.sessionmaker)
        ctx.add_resource_factory(self.create_session, Session,
                                 context_attr=self.session_context_attr)
        logger.info('Configured SQLAlchemy session (default / ctx.%s)',
                    self.session_context_attr)

        await yield_()

        for resource_name, context_attr, engine in self.engines:
            engine.dispose()
            logger.info('SQLAlchemy engine (%s / ctx.%s) shut down', resource_name, context_attr)
