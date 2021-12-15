"""
This module exists to make sure that the testing recipe in the documentation is and stays valid,
and works with different backends.
"""

from contextlib import closing

import pytest
from asphalt.core import ContainerComponent, Context
from sqlalchemy import Column, Integer, Unicode, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from asphalt.sqlalchemy.utils import clear_database

Base = declarative_base()


class Person(Base):
    __tablename__ = 'people'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode(100), nullable=False)


@pytest.fixture(scope='module', params=['sqlite_memory', 'sqlite_file', 'mysql', 'postgresql'])
def connection(request):
    engine = request.getfixturevalue('%s_engine' % request.param)
    conn = engine.connect()

    # Clear any existing tables and create the current tables
    # The clear_database() call can be skipped if your chosen RDBMS supports transactional DDL
    # See https://wiki.postgresql.org/wiki/Transactional_DDL_in_PostgreSQL:_A_Competitive_Analysis
    clear_database(conn)
    Base.metadata.create_all(conn, checkfirst=False)

    yield conn

    conn.close()


@pytest.fixture(scope='module', autouse=True)
def person(connection):
    # Add some base data to the database here (if necessary for your application)
    with closing(Session(connection, expire_on_commit=False)) as session:
        person = Person(name='Test person')
        session.add(person)
        session.commit()
        return person


@pytest.fixture(autouse=True)
def transaction(connection):
    def restart(session):
        # When any session rolls back its transaction, restart this one if it's the one that has
        # been rolled back
        nonlocal tx
        if not connection.in_transaction():
            tx = connection.begin()

    tx = connection.begin()
    event.listen(Session, 'after_rollback', restart)
    yield
    event.remove(Session, 'after_rollback', restart)
    tx.rollback()


@pytest.fixture
async def root_context():
    async with Context() as ctx:
        yield ctx


@pytest.fixture
async def root_component(connection, root_context):
    components = {
        'sqlalchemy': {'bind': connection, 'ready_callback': None}
    }
    component = ContainerComponent(components=components)
    await component.start(root_context)


@pytest.fixture
def dbsession(connection):
    # A database session for use by testing code
    with closing(Session(connection)) as session:
        yield session


@pytest.mark.asyncio
async def test_rollback(dbsession, root_context, root_component):
    # Simulate a rollback happening in a subcontext
    async with Context(root_context) as ctx:
        try:
            # No value for a non-nullable column => IntegrityError!
            ctx.sql.add(Person())
            ctx.sql.flush()
        except IntegrityError:
            # Without the session listener, this row would now be inserted outside a SAVEPOINT,
            # breaking test isolation
            ctx.sql.rollback()
            ctx.sql.add(Person(name='Works now!'))
            ctx.sql.flush()

    # The context is gone, but the extra Person should still be around
    assert dbsession.query(Person).count() == 2


@pytest.mark.asyncio
async def test_add_person(dbsession, root_context, root_component):
    # Simulate adding a row to the "people" table in the application
    async with Context(root_context) as ctx:
        ctx.sql.add(Person(name='Another person'))

    # The testing code should see both rows now
    assert dbsession.query(Person).order_by(Person.id).count() == 2


@pytest.mark.asyncio
async def test_delete_person(dbsession, root_context, root_component):
    # Simulate removing the test person in the application
    async with Context(root_context) as ctx:
        ctx.sql.query(Person).delete()

    # The testing code should not see any rows now
    assert dbsession.query(Person).count() == 0
