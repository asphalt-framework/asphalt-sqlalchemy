from __future__ import annotations

import logging
from asyncio import get_running_loop
from collections.abc import AsyncGenerator, Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from inspect import isawaitable
from typing import Any, cast

from asphalt.core import Component, Context, context_teardown, resolve_reference
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.future.engine import Connection, Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import Pool

from asphalt.sqlalchemy.utils import apply_sqlite_hacks

logger = logging.getLogger(__name__)


class SQLAlchemyComponent(Component):
    """
    Creates resources necessary for accessing relational databases using SQLAlchemy.

    This component supports both synchronous (``sqlite``, ``psycopg2``, etc.) and
    asynchronous (``asyncpg``, ``asyncmy``, etc.) engines, and the provided resources
    differ based on that.

    For synchronous engines, the following resources are provided:

    * :class:`~sqlalchemy.future.engine.Engine`
    * :class:`~sqlalchemy.orm.session.sessionmaker`
    * :class:`~sqlalchemy.orm.session.Session`

    For asynchronous engines, the following resources are provided:

    * :class:`~sqlalchemy.ext.asyncio.AsyncEngine`
    * :class:`~sqlalchemy.orm.session.sessionmaker`
    * :class:`~sqlalchemy.ext.asyncio.AsyncSession`

    .. note:: The following options will always be set to fixed values in sessions:

      * ``expire_on_commit``: ``False``
      * ``future``: ``True``

    :param url: the connection url passed to
        :func:`~sqlalchemy.future.engine.create_engine`
        (can also be a dictionary of :class:`~sqlalchemy.engine.url.URL` keyword
        arguments)
    :param bind: a connection or engine to use instead of creating a new engine
    :param engine_args: extra keyword arguments passed to
        :func:`sqlalchemy.future.engine.create_engine` or
        :func:`sqlalchemy.ext.asyncio.create_engine`
    :param session_args: extra keyword arguments passed to
        :class:`~sqlalchemy.orm.session.Session` or
        :class:`~sqlalchemy.ext.asyncio.AsyncSession`
    :param commit_executor_workers: maximum number of worker threads to use for tearing
        down synchronous sessions (default: 5; ignored for asynchronous engines)
    :param ready_callback: a callable that is called right before the resources are
        added to the context (can be a coroutine function too)
    :param poolclass: the SQLAlchemy pool class (or a textual reference to one) to use;
        passed to :func:`sqlalchemy.future.engine.create_engine` or
        :func:`sqlalchemy.ext.asyncio.create_engine`
    :param resource_name: name space for the database resources
    """

    commit_executor: ThreadPoolExecutor

    def __init__(
        self,
        *,
        url: str | URL | dict[str, Any] | None = None,
        bind: Connection | Engine | AsyncConnection | AsyncEngine | None = None,
        engine_args: dict[str, Any] | None = None,
        session_args: dict[str, Any] | None = None,
        commit_executor_workers: int = 5,
        ready_callback: Callable[[Engine, sessionmaker], Any] | str | None = None,
        poolclass: str | type[Pool] | None = None,
        resource_name: str = "default",
    ):
        self.resource_name = resource_name
        self.commit_executor_workers = commit_executor_workers
        self.ready_callback = resolve_reference(ready_callback)
        engine_args = engine_args or {}
        session_args = session_args or {}
        session_args["expire_on_commit"] = False
        session_args["future"] = True

        if bind:
            self.bind = bind
            self.engine = cast("Engine | AsyncEngine", bind.engine)
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
            try:
                self.engine = self.bind = create_async_engine(
                    url, poolclass=pool_class, **engine_args
                )
            except InvalidRequestError:
                self.engine = self.bind = create_engine(
                    url, poolclass=pool_class, **engine_args
                )

            if url.get_dialect().name == "sqlite":
                apply_sqlite_hacks(self.engine)

        if isinstance(self.engine, AsyncEngine):
            session_args.setdefault("class_", AsyncSession)

        self.sessionmaker = sessionmaker(bind=self.bind, **session_args)

    def create_session(self, ctx: Context) -> Session:
        async def teardown_session(exception: BaseException | None) -> None:
            try:
                if session.in_transaction():
                    context = copy_context()
                    if exception is None:
                        await get_running_loop().run_in_executor(
                            self.commit_executor, context.run, session.commit
                        )
                    else:
                        await get_running_loop().run_in_executor(
                            self.commit_executor, context.run, session.rollback
                        )
            finally:
                session.close()

        session = self.sessionmaker()
        ctx.add_teardown_callback(teardown_session, pass_exception=True)
        return session

    def create_async_session(self, ctx: Context) -> AsyncSession:
        async def teardown_session(exception: BaseException | None) -> None:
            try:
                if session.in_transaction():
                    if exception is None:
                        await session.commit()
                    else:
                        await session.rollback()
            finally:
                await session.close()

        session: AsyncSession = self.sessionmaker()
        ctx.add_teardown_callback(teardown_session, pass_exception=True)
        return session

    @context_teardown
    async def start(self, ctx: Context) -> AsyncGenerator[None, Exception | None]:
        if self.ready_callback:
            retval = self.ready_callback(self.bind, self.sessionmaker)
            if isawaitable(retval):
                await retval

        ctx.add_resource(self.engine, self.resource_name)
        ctx.add_resource(self.sessionmaker, self.resource_name)
        if isinstance(self.engine, AsyncEngine):
            ctx.add_resource_factory(
                self.create_async_session,
                [AsyncSession],
                self.resource_name,
            )
        else:
            self.commit_executor = ThreadPoolExecutor(self.commit_executor_workers)
            ctx.add_teardown_callback(self.commit_executor.shutdown)

            ctx.add_resource_factory(
                self.create_session,
                [Session],
                self.resource_name,
            )

        logger.info(
            "Configured SQLAlchemy resources (%s; dialect=%s, driver=%s)",
            self.resource_name,
            self.bind.dialect.name,
            self.bind.dialect.driver,
        )

        yield

        if isinstance(self.bind, Engine):
            self.bind.dispose()
        elif isinstance(self.bind, AsyncEngine):
            await self.bind.dispose()

        logger.info("SQLAlchemy resources (%s) shut down", self.resource_name)
