"""
This module exists to make sure that the testing recipe in the documentation is and
stays valid, and works with different backends.
"""

import pytest
import pytest_asyncio
from asphalt.core import ContainerComponent, Context
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import delete, func

from asphalt.sqlalchemy.utils import clear_async_database, clear_database

from .model import Base, Person


class TestSyncRecipe:
    @pytest.fixture(scope="class")
    def setup_schema(self, sync_engine):
        clear_database(sync_engine)
        Base.metadata.create_all(sync_engine, checkfirst=False)

    @pytest.fixture
    def connection(self, sync_engine, setup_schema):
        def restart(session, transaction):
            nonlocal nested
            if not nested.is_active:
                nested = conn.begin_nested()

        conn = sync_engine.connect()
        tx = conn.begin()
        nested = conn.begin_nested()
        event.listen(Session, "after_transaction_end", restart)

        yield conn

        event.remove(Session, "after_transaction_end", restart)
        nested.rollback()
        tx.rollback()

    @pytest.fixture(autouse=True)
    def person(self, connection, setup_schema):
        # Add some base data to the database here (if necessary for your application)
        with Session(connection, expire_on_commit=False) as session:
            person = Person(name="Test person")
            session.add(person)
            session.commit()
            return person

    @pytest.fixture
    def root_component(self, connection):
        return ContainerComponent({"sqlalchemy": {"bind": connection}})

    @pytest.fixture
    def dbsession(self, connection):
        # A database session for use by testing code
        with Session(connection) as session:
            yield session

    @pytest.mark.asyncio
    async def test_rollback(self, dbsession, root_component):
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
    async def test_add_person(self, dbsession, root_component):
        # Simulate adding a row to the "people" table in the application
        async with Context() as root_ctx:
            await root_component.start(root_ctx)
            async with Context() as ctx:
                session = ctx.require_resource(Session)
                session.add(Person(name="Another person"))

        # The testing code should see both rows now
        assert dbsession.scalar(func.count(Person.id)) == 2

    @pytest.mark.asyncio
    async def test_delete_person(self, dbsession, root_component):
        # Simulate removing the test person in the application
        async with Context() as root_ctx:
            await root_component.start(root_ctx)
            async with Context() as ctx:
                session = ctx.require_resource(Session)
                session.execute(delete(Person))

        # The testing code should not see any rows now
        assert dbsession.scalar(func.count(Person.id)) == 0


class TestAsyncRecipe:
    @pytest_asyncio.fixture(scope="class")
    async def setup_schema(self, async_engine):
        conn = await async_engine.connect()
        await clear_async_database(conn)
        await conn.run_sync(Base.metadata.create_all, checkfirst=False)
        await conn.commit()
        await conn.close()

    @pytest_asyncio.fixture
    async def connection(self, async_engine, setup_schema):
        def restart(session, transaction):
            nonlocal nested
            if not nested.is_active:
                adapted_connection = conn.sync_connection.connection.dbapi_connection
                nested = adapted_connection.run_async(lambda c: conn.begin_nested())

        conn = await async_engine.connect()
        tx = await conn.begin()
        nested = await conn.begin_nested()
        event.listen(Session, "after_transaction_end", restart)

        yield conn

        event.remove(Session, "after_transaction_end", restart)
        await nested.rollback()
        await tx.rollback()
        await conn.close()

    @pytest_asyncio.fixture(autouse=True)
    async def person(self, connection):
        # Add some base data to the database here (if necessary for your application)
        async with AsyncSession(connection, expire_on_commit=False) as session:
            person = Person(name="Test person")
            session.add(person)
            await session.commit()
            return person

    @pytest.fixture
    def root_component(self, connection):
        return ContainerComponent({"sqlalchemy": {"bind": connection}})

    @pytest_asyncio.fixture
    async def dbsession(self, connection):
        # A database session for use by testing code
        async with AsyncSession(connection) as session:
            yield session

    @pytest.mark.asyncio
    async def test_rollback(self, dbsession, root_component):
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
    async def test_add_person(self, dbsession, root_component):
        # Simulate adding a row to the "people" table in the application
        async with Context() as root_ctx:
            await root_component.start(root_ctx)
            async with Context() as ctx:
                session = ctx.require_resource(AsyncSession)
                session.add(Person(name="Another person"))

        # The testing code should see both rows now
        assert await dbsession.scalar(select(func.count(Person.id))) == 2

    @pytest.mark.asyncio
    async def test_delete_person(self, dbsession, root_component):
        # Simulate removing the test person in the application
        async with Context() as root_ctx:
            await root_component.start(root_ctx)
            async with Context() as ctx:
                session = ctx.require_resource(AsyncSession)
                await session.execute(delete(Person))

        # The testing code should not see any rows now
        assert await dbsession.scalar(func.count(Person.id)) == 0
