"""
This module exists to make sure that the testing recipe in the documentation is and
stays valid, and works with different backends.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import pytest_asyncio
from asphalt.core import ContainerComponent, Context
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import delete, func, select

from asphalt.sqlalchemy.utils import clear_async_database, clear_database

from .model import Base, Person


class TestSyncRecipe:
    @pytest.fixture
    def connection(self, sync_engine: Engine) -> Generator[Connection, Any, None]:
        with sync_engine.connect() as conn:
            if conn.dialect.name == "mysql":
                clear_database(conn)

            Base.metadata.create_all(conn, checkfirst=False)
            yield conn

    @pytest.fixture(autouse=True)
    def nested_tx(self, connection: Connection) -> Generator[None, Any, None]:
        tx = connection.begin_nested()
        yield
        tx.rollback()

    @pytest.fixture(autouse=True)
    def person(self, connection: Connection) -> Person:
        # Add some base data to the database here (if necessary for your application)
        with Session(connection, expire_on_commit=False) as session:
            person = Person(name="Test person")
            session.add(person)
            session.commit()
            return person

    @pytest.fixture
    def root_component(self, connection: Connection) -> ContainerComponent:
        return ContainerComponent({"sqlalchemy": {"bind": connection}})

    @pytest.fixture
    def dbsession(self, connection: Connection) -> Generator[Session, Any, None]:
        # A database session for use by testing code
        with Session(connection) as session:
            yield session

    @pytest.mark.asyncio
    async def test_rollback(
        self, dbsession: Session, root_component: ContainerComponent
    ) -> None:
        # Simulate a rollback happening in a subcontext
        async with Context() as root_ctx:
            await root_component.start(root_ctx)
            async with Context() as ctx:
                session = ctx.require_resource(Session)
                try:
                    # No value for a non-nullable column => IntegrityError!
                    session.add(Person())
                    session.flush()
                except IntegrityError:
                    # Without the session listener, this row would now be inserted
                    # outside a SAVEPOINT, breaking test isolation
                    session.rollback()
                    session.add(Person(name="Works now!"))
                    session.flush()

        # The context is gone, but the extra Person should still be around
        assert dbsession.scalar(func.count(Person.id)) == 2

    @pytest.mark.asyncio
    async def test_add_person(
        self, dbsession: Session, root_component: ContainerComponent
    ) -> None:
        # Simulate adding a row to the "people" table in the application
        async with Context() as root_ctx:
            await root_component.start(root_ctx)
            async with Context() as ctx:
                session = ctx.require_resource(Session)
                session.add(Person(name="Another person"))

        # The testing code should see both rows now
        assert dbsession.scalar(func.count(Person.id)) == 2

    @pytest.mark.asyncio
    async def test_delete_person(
        self, dbsession: Session, root_component: ContainerComponent
    ) -> None:
        # Simulate removing the test person in the application
        async with Context() as root_ctx:
            await root_component.start(root_ctx)
            async with Context() as ctx:
                session = ctx.require_resource(Session)
                session.execute(delete(Person))

        # The testing code should not see any rows now
        assert dbsession.scalar(func.count(Person.id)) == 0


class TestAsyncRecipe:
    @pytest_asyncio.fixture
    async def connection(
        self, async_engine: AsyncEngine
    ) -> AsyncGenerator[AsyncConnection, Any]:
        async with async_engine.connect() as conn:
            if conn.dialect.name == "mysql":
                await clear_async_database(conn)

            await conn.run_sync(Base.metadata.create_all, checkfirst=False)
            yield conn

    @pytest_asyncio.fixture(autouse=True)
    async def nested_tx(self, connection: AsyncConnection) -> AsyncGenerator[None, Any]:
        nested = await connection.begin_nested()
        yield
        await nested.rollback()

    @pytest_asyncio.fixture(autouse=True)
    async def person(self, connection: AsyncConnection) -> Person:
        # Add some base data to the database here (if necessary for your application)
        async with AsyncSession(connection, expire_on_commit=False) as session:
            person = Person(name="Test person")
            session.add(person)
            await session.commit()
            return person

    @pytest.fixture
    def root_component(self, connection: AsyncConnection) -> ContainerComponent:
        return ContainerComponent({"sqlalchemy": {"bind": connection}})

    @pytest_asyncio.fixture
    async def dbsession(
        self, connection: AsyncConnection
    ) -> AsyncGenerator[AsyncSession, Any]:
        # A database session for use by testing code
        async with AsyncSession(connection) as session:
            yield session

    @pytest.mark.asyncio
    async def test_rollback(
        self, dbsession: AsyncSession, root_component: ContainerComponent
    ) -> None:
        # Simulate a rollback happening in a subcontext
        async with Context() as root_ctx:
            await root_component.start(root_ctx)
            async with Context() as ctx:
                session = ctx.require_resource(AsyncSession)
                try:
                    # No value for a non-nullable column => IntegrityError!
                    session.add(Person())
                    await session.flush()
                except IntegrityError:
                    # Without the session listener, this row would now be inserted
                    # outside a SAVEPOINT, breaking test isolation
                    await session.rollback()
                    session.add(Person(name="Works now!"))
                    await session.flush()

        # The context is gone, but the extra Person should still be around
        assert await dbsession.scalar(func.count(Person.id)) == 2

    @pytest.mark.asyncio
    async def test_add_person(
        self, dbsession: AsyncSession, root_component: ContainerComponent
    ) -> None:
        # Simulate adding a row to the "people" table in the application
        async with Context() as root_ctx:
            await root_component.start(root_ctx)
            async with Context() as ctx:
                session = ctx.require_resource(AsyncSession)
                session.add(Person(name="Another person"))

        # The testing code should see both rows now
        assert await dbsession.scalar(select(func.count(Person.id))) == 2

    @pytest.mark.asyncio
    async def test_delete_person(
        self, dbsession: AsyncSession, root_component: ContainerComponent
    ) -> None:
        # Simulate removing the test person in the application
        async with Context() as root_ctx:
            await root_component.start(root_ctx)
            async with Context() as ctx:
                session = ctx.require_resource(AsyncSession)
                await session.execute(delete(Person))

        # The testing code should not see any rows now
        assert await dbsession.scalar(func.count(Person.id)) == 0
