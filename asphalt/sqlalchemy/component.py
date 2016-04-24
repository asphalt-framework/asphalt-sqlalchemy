import logging
from contextlib import closing
from typing import Dict, Any, Union

from asyncio_extras.threads import call_in_executor
from sqlalchemy.engine import create_engine, Engine
from sqlalchemy.engine.interfaces import Connectable
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql.schema import MetaData
from typeguard import check_argument_types

from asphalt.core import Component, Context, resolve_reference, merge_config

logger = logging.getLogger(__name__)


class SQLAlchemyComponent(Component):
    """
    Publishes one or more :class:`sqlalchemy.engine.Engine` resources and context variables.

    Unless sessions are disabled (``session=False``), it additionally publishes one
    :class:`sqlalchemy.orm.session.sessionmaker` resource and one session (of type
    :class:`sqlalchemy.orm.session.Session`) as a lazy resource.

    If only a single engine is defined, it will be bound to the session (if configured).
    If multiple engines are defined, any calls to :meth:`~sqlalchemy.orm.session.Session.execute`
    require the engine to be passed as the ``bind`` argument.

    If ``engines`` is defined, any extra keyword arguments are used as default values for
    :meth:`configure_engine` for all engines (:func:`~asphalt.core.util.merge_config` is used to
    merge the per-engine arguments with the defaults). Otherwise, a single engine is created based
    on the provided default arguments, with ``context_attr`` defaulting to ``sql``.

    :param engines: a dictionary of resource name ⭢ keyword arguments passed to
        :meth:`configure_engine`
    :param session: either a boolean (``True`` enables the session with default settings, ``False``
        skips session configuration) or a dictionary of session options, passed to
        :meth:`configure_sessionmaker`
    :param default_engine_args: default values for :meth:`configure_engine`
    """

    session_context_attr = sessionmaker = None

    def __init__(self, engines: Dict[str, Dict[str, Any]] = None, session: Dict[str, Any] = True,
                 **default_engine_args):
        assert check_argument_types()
        if not engines:
            default_engine_args.setdefault('context_attr', 'sql')
            engines = {'default': default_engine_args}

        self.connectables = []
        for resource_name, config in engines.items():
            config = merge_config(default_engine_args, config)
            config.setdefault('context_attr', resource_name)
            context_attr, bind = self.configure_engine(**config)
            self.connectables.append((resource_name, context_attr, bind))

        if session is not False:
            session = {} if session is True else session
            if len(self.connectables) == 1:
                session.setdefault('bind', self.connectables[0][-1])

            self.session_context_attr, self.sessionmaker = self.configure_sessionmaker(**session)

    @classmethod
    def configure_sessionmaker(cls, context_attr: str = 'dbsession', **session_args):
        """
        Create the session factory.

        :param context_attr: context attribute for lazily created sessions
        :param session_args: keyword arguments passed directly to
            :class:`~sqlalchemy.orm.session.sessionmaker`

        """
        assert check_argument_types()
        return context_attr, sessionmaker(**session_args)

    @classmethod
    def configure_engine(cls, context_attr: str = None, metadata: Union[str, MetaData] = None,
                         url: Union[str, URL, Dict[str, Any]] = None, bind: Connectable = None,
                         **engine_args):
        """
        Create an engine and optionally bind it to a :class:`~sqlalchemy.schema.MetaData`.

        If both ``url`` and ``bind`` are provided, the ``bind`` parameter takes priority.

        :param context_attr: context attribute for the engine
        :param metadata: a metadata object to bind to
        :param url: the connection url passed to :func:`~sqlalchemy.create_engine`
            (can also be a dictionary of :class:`~sqlalchemy.engine.url.URL` keyword arguments)
        :param bind: a connection or engine instance to use instead of creating a new engine
        :param engine_args: keyword arguments passed to :func:`~sqlalchemy.create_engine`

        """
        assert check_argument_types()
        if url and not bind:
            if isinstance(url, dict):
                url = URL(**url)
            elif isinstance(url, str):
                url = make_url(url)

            # This is a hack to get SQLite to play nice with asphalt-sqlalchemy's juggling of
            # connections between multiple threads. The same connection should, however, never be
            # used in multiple threads at once.
            if url.drivername.split('+')[0] == 'sqlite':
                connect_args = engine_args.setdefault('connect_args', {})
                connect_args.setdefault('check_same_thread', False)

            bind = create_engine(url, **engine_args)
        elif not bind:
            raise ValueError('specify either url or bind')

        if metadata:
            metadata = resolve_reference(metadata)
            assert isinstance(metadata, MetaData)
            metadata.bind = bind

        return context_attr, bind

    def create_session(self, ctx: Context):
        async def handler_finished(event):
            with closing(session):
                if event.exception is None and session.is_active:
                    await call_in_executor(session.commit)

        session = self.sessionmaker(info={'ctx': ctx})
        ctx.finished.connect(handler_finished)
        return session

    async def start(self, ctx: Context):
        for resource_name, context_attr, bind in self.connectables:
            ctx.publish_resource(bind, resource_name, context_attr, types=Engine)
            logger.info('Configured SQLAlchemy engine (%s / ctx.%s; dialect=%s)', resource_name,
                        context_attr, bind.dialect.name)

        if self.sessionmaker:
            ctx.publish_resource(self.sessionmaker)
            ctx.publish_lazy_resource(self.create_session, Session,
                                      context_attr=self.session_context_attr)
            logger.info('Configured SQLAlchemy session (default / ctx.%s)',
                        self.session_context_attr)
