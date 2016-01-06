from asyncio import coroutine
from contextlib import closing
from typing import Dict, Any, Union
import logging

from typeguard import check_argument_types
from sqlalchemy.engine import create_engine, Engine
from sqlalchemy.engine.interfaces import Connectable
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql.schema import MetaData
from asphalt.core.component import Component
from asphalt.core.context import Context, ContextFinishEvent
from asphalt.core.util import resolve_reference, blocking

from .async import AsyncSession

logger = logging.getLogger(__name__)


class SQLAlchemyComponent(Component):
    """
    Provides SQLAlchemy integration.

    Publishes one or more :class:`sqlalchemy.engine.Engine` resources and context variables.

    Unless sessions are disabled (``session=False``), it additionally publishes one
    :class:`sqlalchemy.orm.session.sessionmaker` resource and one session (of type
    :class:`sqlalchemy.orm.session.Session`) as a lazy resource and context variable.

    If only a single engine is defined, it will be bound to the session (if configured).
    If multiple engines are defined, any calls to :meth:`~sqlalchemy.orm.session.Session.execute`
    require the engine to be passed as the ``bind`` argument.

    :param engines: a dictionary of resource name -> keyword arguments passed to
        :meth:`create_engine`
    :param session: either a boolean (``True`` enables the session with default settings, ``False``
        skips session configuration) or a dictionary of session options, passed to
        :meth:`create_sessionmaker`
    :param default_engine_args: :meth:`create_engine` arguments for the default engine
    """

    session_context_attr = sessionmaker = None

    def __init__(self, engines: Dict[str, Dict[str, Any]]=None, session: Dict[str, Any]=True,
                 **default_engine_args):
        check_argument_types()
        if engines and default_engine_args:
            raise ValueError('specify either an "engines" dictionary or the default engine\'s '
                             'options directly, but not both')

        if not engines:
            default_engine_args.setdefault('context_attr', 'sql')
            engines = {'default': default_engine_args}

        self.engines = []
        for resource_name, config in engines.items():
            config.setdefault('context_attr', resource_name)
            self.engines.append((resource_name,) + self.create_engine(**config))

        if session is not False:
            session = {} if session is True else session
            if len(self.engines) == 1:
                session.setdefault('bind', self.engines[0][-1])

            self.session_context_attr, self.sessionmaker = self.create_sessionmaker(**session)

    @classmethod
    def create_sessionmaker(cls, context_attr: str='dbsession', **session_args):
        """
        Configure the session factory.

        :param context_attr: context attribute for lazily created sessions
        :param session_args: keyword arguments passed directly to
            :class:`~sqlalchemy.orm.session.sessionmaker`

        """
        check_argument_types()
        session_args.setdefault('class_', AsyncSession)
        return context_attr, sessionmaker(**session_args)

    @classmethod
    def create_engine(cls, context_attr: str, metadata: Union[str, MetaData]=None, url: str=None,
                      bind: Connectable=None, **engine_args):
        """
        Create an engine and optionally bind it to a :class:`~sqlalchemy.schema.MetaData`.

        If both ``url`` and ``bind`` are provided, the ``bind`` parameter takes priority.

        :param context_attr: context attribute for the engine
        :param metadata: a metadata object to bind to
        :param url: the connection url passed to :func:`~sqlalchemy.create_engine`
        :param bind: a connection or engine instance to use instead of creating a new engine
        :param engine_args: keyword arguments passed to :func:`~sqlalchemy.create_engine`

        """
        check_argument_types()
        if url and not bind:
            engine_args.setdefault('strategy', 'async')

            # This is a hack to get SQLite to play nice with asphalt-sqlalchemy's juggling of
            # connections between multiple threads. The same connection should, however, never be
            # used in multiple threads at once.
            if url.startswith('sqlite'):
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

    @coroutine
    def start(self, ctx: Context):
        for resource_name, context_attr, engine in self.engines:
            yield from ctx.publish_resource(engine, resource_name, context_attr, types=Engine)
            logger.info('Configured SQLAlchemy engine (%s / ctx.%s; dialect=%s)', resource_name,
                        context_attr, engine.dialect.name)

        if self.sessionmaker:
            yield from ctx.publish_resource(self.sessionmaker)
            yield from ctx.publish_lazy_resource(self.create_session, Session,
                                                 context_attr=self.session_context_attr)
            logger.info('Configured SQLAlchemy session (default / ctx.%s)',
                        self.session_context_attr)

    def create_session(self, ctx: Context):
        @blocking
        def handler_finished(event: ContextFinishEvent):
            with closing(session):
                if event.exception is None and session.is_active:
                    session.commit()

        session = self.sessionmaker(info={'ctx': ctx})
        ctx.add_listener('finished', handler_finished)
        return session
