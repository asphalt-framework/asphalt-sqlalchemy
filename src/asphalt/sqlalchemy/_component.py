from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from inspect import isawaitable
from typing import Any, cast

from anyio import CapacityLimiter, to_thread
from asphalt.core import (
    Component,
    add_resource,
    add_resource_factory,
    add_teardown_callback,
    qualified_name,
    resolve_reference,
)

from asphalt.sqlalchemy._utils import apply_sqlite_hacks
from sqlalchemy.engine import Connection, Engine, create_engine
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import Pool

logger = logging.getLogger(__name__)


class SQLAlchemyComponent(Component):
    """
    Creates resources necessary for accessing relational databases using SQLAlchemy.

    This component supports both synchronous (``sqlite``, ``psycopg2``, etc.) and
    asynchronous (``asyncpg``, ``asyncmy``, etc.) engines, and the provided resources
    differ based on that.

    For synchronous engines, the following resources are provided:

    * :class:`~sqlalchemy.engine.Engine`
    * :class:`~sqlalchemy.orm.session.sessionmaker`
    * :class:`~sqlalchemy.orm.session.Session`

    For asynchronous engines, the following resources are provided:

    * :class:`~sqlalchemy.ext.asyncio.AsyncEngine`
    * :class:`~sqlalchemy.orm.session.sessionmaker`
    * :class:`~sqlalchemy.ext.asyncio.async_sessionmaker`
    * :class:`~sqlalchemy.ext.asyncio.AsyncSession`

    .. note:: The following options will always be set to fixed values in sessions:

      * ``expire_on_commit``: ``False``

    :param url: the connection url passed to
        :func:`~sqlalchemy.engine.create_engine`
        (can also be a dictionary of :class:`~sqlalchemy.engine.url.URL` keyword
        arguments)
    :param bind: a connection or engine to use instead of creating a new engine
    :param prefer_async: if ``True``, try to create an async engine rather than a
        synchronous one, in cases like ``psycopg`` where the driver supports both
    :param engine_args: extra keyword arguments passed to
        :func:`sqlalchemy.engine.create_engine` or
        :func:`sqlalchemy.ext.asyncio.create_engine`
    :param session_args: extra keyword arguments passed to
        :class:`~sqlalchemy.orm.session.Session` or
        :class:`~sqlalchemy.ext.asyncio.AsyncSession`
    :param commit_executor_workers: maximum number of worker threads to use for tearing
        down synchronous sessions (default: 5; ignored for asynchronous engines)
    :param ready_callback: a callable that is called right before the resources are
        added to the context (can be a coroutine function too)
    :param poolclass: the SQLAlchemy pool class (or a textual reference to one) to use;
        passed to :func:`sqlalchemy.engine.create_engine` or
        :func:`sqlalchemy.ext.asyncio.create_engine`
    :param resource_name: name space for the database resources
    """

    _engine: Engine | AsyncEngine
    _bind: Connection | Engine
    _async_bind: AsyncConnection | AsyncEngine

    def __init__(
        self,
        *,
        url: str | URL | dict[str, Any] | None = None,
        bind: Connection | Engine | AsyncConnection | AsyncEngine | None = None,
        prefer_async: bool = True,
        engine_args: dict[str, Any] | None = None,
        session_args: dict[str, Any] | None = None,
        commit_executor_workers: int = 50,
        ready_callback: Callable[[Engine, sessionmaker[Any]], Any] | str | None = None,
        poolclass: str | type[Pool] | None = None,
        resource_name: str = "default",
    ):
        self.resource_name = resource_name
        self.commit_thread_limiter = CapacityLimiter(commit_executor_workers)
        self.ready_callback = resolve_reference(ready_callback)
        engine_args = engine_args or {}
        session_args = session_args or {}
        session_args["expire_on_commit"] = False

        if bind:
            if isinstance(bind, Connection):
                self._bind = bind
                self._engine = bind.engine
            elif isinstance(bind, AsyncConnection):
                self._async_bind = bind
                self._engine = bind.engine
            elif isinstance(bind, Engine):
                self._engine = self._bind = bind
            elif isinstance(bind, AsyncEngine):
                self._engine = self._async_bind = bind
            else:
                raise TypeError(f"Incompatible bind argument: {qualified_name(bind)}")
        else:
            if isinstance(url, dict):
                url = URL.create(**url)
            elif isinstance(url, str):
                url = make_url(url)
            elif url is None:
                raise TypeError('both "url" and "bind" cannot be None')

            # This is a hack to get SQLite to play nice with asphalt-sqlalchemy's
            # juggling of connections between multiple threads. The same connection
            # should, however, never be used in multiple threads at once.
            if url.get_dialect().name == "sqlite":
                connect_args = engine_args.setdefault("connect_args", {})
                connect_args.setdefault("check_same_thread", False)

            if isinstance(poolclass, str):
                poolclass = resolve_reference(poolclass)

            pool_class = cast("type[Pool]", poolclass)
            if prefer_async:
                try:
                    self._engine = self._async_bind = create_async_engine(
                        url, poolclass=pool_class, **engine_args
                    )
                except InvalidRequestError:
                    self._engine = self._bind = create_engine(
                        url, poolclass=pool_class, **engine_args
                    )
            else:
                try:
                    self._engine = self._bind = create_engine(
                        url, poolclass=pool_class, **engine_args
                    )
                except InvalidRequestError:
                    self._engine = self._async_bind = create_async_engine(
                        url, poolclass=pool_class, **engine_args
                    )

            if url.get_dialect().name == "sqlite":
                apply_sqlite_hacks(self._engine)

        if isinstance(self._engine, AsyncEngine):
            # This is needed for listening to ORM events when async sessions are used
            self._sessionmaker = sessionmaker()
            self._async_sessionmaker = async_sessionmaker(
                bind=self._async_bind,
                sync_session_class=self._sessionmaker,
                **session_args,
            )
        else:
            self._sessionmaker = sessionmaker(bind=self._bind, **session_args)

    def create_session(self) -> Session:
        async def teardown_session() -> None:
            try:
                if session.in_transaction():
                    if sys.exc_info()[1] is None:
                        await to_thread.run_sync(
                            session.commit, limiter=self.commit_thread_limiter
                        )
                    else:
                        await to_thread.run_sync(
                            session.rollback, limiter=self.commit_thread_limiter
                        )
            finally:
                session.close()

        session = self._sessionmaker()
        add_teardown_callback(teardown_session)
        return session

    def create_async_session(self) -> AsyncSession:
        async def teardown_session() -> None:
            try:
                if session.in_transaction():
                    if sys.exc_info()[1] is None:
                        await session.commit()
                    else:
                        await session.rollback()
            finally:
                await session.close()

        session: AsyncSession = self._async_sessionmaker()
        add_teardown_callback(teardown_session)
        return session

    async def start(self) -> None:
        bind: Connection | Engine | AsyncConnection | AsyncEngine
        if isinstance(self._engine, AsyncEngine):
            if self.ready_callback:
                retval = self.ready_callback(self._async_bind, self._sessionmaker)
                if isawaitable(retval):
                    await retval

            bind = self._async_bind
            if isinstance(bind, AsyncEngine):
                teardown_callback = self._engine.dispose
            else:
                teardown_callback = None

            add_resource(
                self._engine,
                self.resource_name,
                description="SQLAlchemy engine (asynchronous)",
                teardown_callback=teardown_callback,
            )
            add_resource(
                self._sessionmaker,
                self.resource_name,
                description="SQLAlchemy session factory (synchronous)",
            )
            add_resource(
                self._async_sessionmaker,
                self.resource_name,
                description="SQLAlchemy session factory (asynchronous)",
            )
            add_resource_factory(
                self.create_async_session,
                self.resource_name,
                description="SQLAlchemy session (asynchronous)",
            )
        else:
            if self.ready_callback:
                retval = self.ready_callback(self._bind, self._sessionmaker)
                if isawaitable(retval):
                    await retval

            bind = self._bind
            if isinstance(bind, AsyncEngine):
                teardown_callback = self._engine.dispose
            else:
                teardown_callback = None

            add_resource(
                self._engine,
                self.resource_name,
                description="SQLAlchemy engine (synchronous)",
                teardown_callback=teardown_callback,
            )
            add_resource(
                self._sessionmaker,
                self.resource_name,
                description="SQLAlchemy session factory (synchronous)",
            )
            add_resource_factory(
                self.create_session,
                self.resource_name,
                description="SQLAlchemy session (synchronous)",
            )

        logger.info(
            "Configured SQLAlchemy resources (%s; dialect=%s, driver=%s)",
            self.resource_name,
            bind.dialect.name,
            bind.dialect.driver,
        )
