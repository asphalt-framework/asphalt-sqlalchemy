import logging
from concurrent.futures import Executor, ThreadPoolExecutor
from functools import partial
from inspect import isawaitable
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from asphalt.core import (
    Component, Context, context_teardown, executor, merge_config, resolve_reference)
from sqlalchemy.engine import Connection, Engine, create_engine
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import Pool
from typeguard import check_argument_types

logger = logging.getLogger(__name__)

if hasattr(URL, 'create'):
    # SQLAlchemy 1.4
    create_url = URL.create
else:
    create_url = URL


class SQLAlchemyComponent(Component):
    """
    Creates resources necessary for accessing relational databases using SQLAlchemy.

    For every configured engine, this component will create the following resources:

    * one :class:`~sqlalchemy.engine.Engine` resource
    * one :class:`~sqlalchemy.orm.session.sessionmaker` resource
    * one :class:`~sqlalchemy.orm.session.Session` resource factory

    If ``engines`` is not provided, a single engine/session will be created using by passing any
    leftover constructor keyword arguments to :meth:`~create_engine`. The session will then be
    available as ``ctx.sql`` by default.

    When multiple engines have been specified, the context attributes of their corresponding
    sessions will match the resource names by default.

    .. note:: The ``expire_on_commit`` option in sessions is set to ``False`` by default.

    :param engines: a dictionary of resource name ⭢ keyword arguments passed to
        :meth:`configure_engine`
    :param session: keyword arguments passed to :class:`~sqlalchemy.orm.session.sessionmaker`
    :param commit_executor: an :class:`~concurrent.futures.Executor` or the resource name of one
        (if not specified, a :class:`~concurrent.futures.ThreadPoolExecutor` with 5 workers is
        created)
    :param commit_executor_workers: number of worker threads in the implicitly created commit
        executor (ignored if ``commit_executor`` is given)
    :param default_args: default values for :meth:`configure_engine`
    """

    def __init__(self, engines: Dict[str, Dict[str, Any]] = None,
                 commit_executor: Union[Executor, str] = None, commit_executor_workers: int = 5,
                 **default_args) -> None:
        assert check_argument_types()
        if not engines:
            default_args.setdefault('context_attr', 'sql')
            engines = {'default': default_args}

        self.session_factories = []  # type: List[Tuple]
        for resource_name, config in engines.items():
            config = merge_config(default_args, config)
            context_attr = config.pop('context_attr', resource_name)
            bind, session_factory, ready_callback = self.configure_engine(**config)
            self.session_factories.append(
                (resource_name, context_attr, bind, session_factory, ready_callback))

        self.commit_executor = commit_executor
        self.commit_executor_workers = commit_executor_workers

    @classmethod
    def configure_engine(cls, url: Union[str, URL, Dict[str, Any]] = None,
                         bind: Union[Connection, Engine] = None, session: Dict[str, Any] = None,
                         ready_callback: Union[Callable[[Engine, sessionmaker], Any], str] = None,
                         poolclass: Union[str, Pool] = None, **engine_args):
        """
        Create an engine and selectively apply certain hacks to make it Asphalt friendly.

        :param url: the connection url passed to :func:`~sqlalchemy.create_engine`
            (can also be a dictionary of :class:`~sqlalchemy.engine.url.URL` keyword arguments)
        :param bind: a connection or engine to use instead of creating a new engine
        :param session: keyword arguments to :class:`~sqlalchemy.orm.session.sessionmaker`
        :param ready_callback: callable (or a ``module:varname`` reference to one) called with two
            arguments: the Engine and the sessionmaker when the component is started but before the
            resources are added to the context
        :param poolclass: the SQLAlchemy Pool class to use; passed to
            :func:`~sqlalchemy.create_engine`
        :param engine_args: keyword arguments passed to :func:`~sqlalchemy.create_engine`

        """
        assert check_argument_types()
        if bind is None:
            if isinstance(url, dict):
                url = create_url(**url)
            elif isinstance(url, str):
                url = make_url(url)
            elif url is None:
                raise TypeError('both "url" and "bind" cannot be None')

            if isinstance(poolclass, str):
                poolclass = resolve_reference(poolclass)

            # This is a hack to get SQLite to play nice with asphalt-sqlalchemy's juggling of
            # connections between multiple threads. The same connection should, however, never be
            # used in multiple threads at once.
            if url.get_dialect().name == 'sqlite':
                connect_args = engine_args.setdefault('connect_args', {})
                connect_args.setdefault('check_same_thread', False)

            bind = create_engine(url, poolclass=poolclass, **engine_args)

        session = session or {}
        session.setdefault('expire_on_commit', False)
        ready_callback = resolve_reference(ready_callback)
        return bind, sessionmaker(bind, **session), ready_callback

    def create_session(self, ctx: Context, factory: sessionmaker) -> Session:
        @executor(self.commit_executor)
        def teardown_session(exception: Optional[BaseException]) -> None:
            try:
                if exception is None and session.is_active:
                    session.commit()
            finally:
                session.close()
                del session.info['ctx']

        session = factory(info={'ctx': ctx})
        ctx.add_teardown_callback(teardown_session, pass_exception=True)
        return session

    @context_teardown
    async def start(self, ctx: Context):
        if isinstance(self.commit_executor, str):
            self.commit_executor = await ctx.request_resource(Executor, self.commit_executor)
        elif self.commit_executor is None:
            self.commit_executor = ThreadPoolExecutor(self.commit_executor_workers)
            ctx.add_teardown_callback(self.commit_executor.shutdown)

        for resource_name, context_attr, bind, factory, ready_callback in self.session_factories:
            if ready_callback:
                retval = ready_callback(bind, factory)
                if isawaitable(retval):
                    await retval

            engine = bind if isinstance(bind, Engine) else bind.engine
            ctx.add_resource(engine, resource_name)
            ctx.add_resource(factory, resource_name)
            ctx.add_resource_factory(partial(self.create_session, factory=factory),
                                     [Session], resource_name, context_attr)
            logger.info('Configured SQLAlchemy session maker (%s / ctx.%s; dialect=%s)',
                        resource_name, context_attr, bind.dialect.name)

        yield

        for resource_name, context_attr, bind, factory, ready_callback in self.session_factories:
            if isinstance(bind, Engine):
                bind.dispose()

            logger.info('SQLAlchemy session maker (%s / ctx.%s) shut down', resource_name,
                        context_attr)
