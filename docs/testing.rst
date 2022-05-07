Testing with asphalt-sqlalchemy
===============================

Testing database using code usually involves one of two approaches: either you mock your
database connections and return fake data, or you test against a real database engine.
This document focuses on the latter approach and provides instructions for setting up
your fixtures accordingly.

The basic idea is to have a session level fixture which creates and engine and then
makes a single connection, through which all the database interaction will happen during
the testing session. It should first remove any previously created tables and then
create the tables from scratch, using the current metadata. This ensures that even if
the testing session was interrupted previously, the correct set of tables are always
properly created. Then, during every test a transaction is started and then rolled back
after the tests, thus ensuring test isolation.

In order to force all database interactions to happen within the same transaction, the
``sqlalchemy`` component is passed the :class:`~sqlalchemy.future.engine.Connection`
instance created by the connection fixture as the ``bind`` option. This will override
any ``url`` option passed to the component. When the session's ``bind`` is a
:class:`~sqlalchemy.future.engine.Connection` and not an
:class:`~sqlalchemy.future.engine.Engine`, it will not attempt to actually commit the
transaction. However, special measures must be taken if the application code ever rolls
back the transaction. Unlike ``commit()``, a ``rollback()`` call from a session does end
the underlying transaction. To counter that, a session listener must be set up which
restarts the transaction immediately after a session rolls it back.

This technique is based on a chapter of `SQLAlchemy documentation`_ dealing with
testing.

.. note:: Always test against the same kind of database(s) as you're deploying on!
    Otherwise you may see unwarranted errors, or worse, passing tests that should have
    failed.

.. _SQLAlchemy documentation: https://docs.sqlalchemy.org/en/14/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites

Setting up the SQLAlchemy component and the database connection
---------------------------------------------------------------

This assumes the following:

* You are using `pytest`_ for testing
* You have the necessary testing dependencies installed (``pytest``, ``pytest-asyncio``)
* You have a package ``yourapp.models`` and a declarative base class (``Base``) in it
* You have model class named ``Person`` in ``yourapp.models``
* You have a test database accessible (not required with SQLite)
* You have a project subdirectory for tests (named ``tests`` here)

The following fixtures should go in the ``conftest.py`` file in your ``tests`` folder.
They ensure that any changes made to the database are rolled back at the end of each
test.

See the ``tests/test_testing_recipe`` module in the source code for a more complete
example.

.. _pytest: https://pytest.org

.. tabs::

   .. tab:: Asynchronous

      .. tabs::

         .. code-tab:: python3 conftest.py

            from asyncio import new_event_loop, set_event_loop

            import pytest
            import pytest_asyncio
            from asphalt.sqlalchemy.utils import clear_async_database
            from sqlalchemy import create_engine, event
            from sqlalchemy.ext.asyncio import AsyncSession
            from sqlalchemy.orm import Session

            from yourapp.component import ApplicationComponent
            from yourapp.models import Base, Person


            @pytest.fixture(scope="session")
            def event_loop():
                # Required for session scoped async fixtures; only works with pytest-asyncio
                loop = new_event_loop()
                set_event_loop(loop)
                yield loop
                loop.close()


            @pytest.fixture(scope="session")
            def sqla_engine():
                # For SQLite, some additional hacks are required:
                #
                # from asphalt.sqlalchemy.utils import apply_sqlite_hacks
                # engine = create_engine("sqlite+aiosqlite:///:memory:")
                # apply_sqlite_hacks(engine)
                engine = create_engine("postgresql+asyncpg://user:password@localhost/test")
                yield engine
                engine.dispose()


            @pytest_asyncio.fixture(scope="session")
            async def setup_schema(sqla_engine):
                conn = await sqla_engine.connect()
                await clear_async_database(conn)
                await conn.run_sync(Base.metadata.create_all, checkfirst=False)
                await conn.commit()
                await conn.close()


            @pytest_asyncio.fixture(scope="session", autouse=True)
            def person(sqla_engine, setup_schema):
                # Add some base data to the database here (if necessary for your application)
                async with AsyncSession(sqla_engine, expire_on_commit=False) as session:
                    person = Person(name="Test person")
                    session.add(person)
                    await session.commit()
                    return person


            @pytest_asyncio.fixture
            async def connection(sqla_engine):
                def restart(session, transaction):
                    nonlocal nested
                    if not nested.is_active:
                        adapted_connection = (
                            conn.sync_connection.connection.dbapi_connection
                        )
                        nested = adapted_connection.run_async(
                            lambda c: conn.begin_nested()
                        )

                conn = await sqla_engine.connect()
                tx = await conn.begin()
                nested = await conn.begin_nested()
                event.listen(Session, "after_transaction_end", restart)

                yield conn

                event.remove(Session, "after_transaction_end", restart)
                await nested.rollback()
                await tx.rollback()
                await conn.close()


            @pytest.fixture
            def root_component(connection):
                return ApplicationComponent({"sqlalchemy": {"bind": connection}})


            @pytest_asyncio.fixture
            async def dbsession(connection):
                # A database session for use by testing code
                async with AsyncSession(connection) as session:
                    yield session

         .. code-tab:: python3 test_component.py

             import pytest
             from asphalt.core import Context


             @pytest.mark.asyncio
             async def test_func(root_component, dbsession):
                 """This is an actual test function which uses the database connection."""
                 async with Context() as ctx:
                     await root_component.start(ctx)
                     ...

   .. tab:: Synchronous

      .. tabs::

         .. code-tab:: python3 conftest.py

             import pytest
             from asphalt.sqlalchemy.utils import clear_database
             from sqlalchemy import create_engine, event
             from sqlalchemy.orm import Session

             from yourapp.component import ApplicationComponent
             from yourapp.models import Base, Person


             @pytest.fixture(scope="session")
             def sqla_engine():
                 # For SQLite, some additional hacks are required:
                 #
                 # from asphalt.sqlalchemy.utils import apply_sqlite_hacks
                 # engine = create_engine(
                 #     "sqlite:///:memory:",
                 #     connect_args={"check_same_thread": False}
                 # )
                 # apply_sqlite_hacks(engine)
                 engine = create_engine("postgresql+psycopg2://user:password@localhost/test")
                 yield engine
                 engine.dispose()


             @pytest.fixture(scope="session")
             def setup_schema(sqla_engine):
                 conn = sqla_engine.connect()
                 clear_database(conn)
                 conn.run_sync(Base.metadata.create_all, checkfirst=False)
                 conn.commit()
                 conn.close()


             @pytest.fixture(scope="session", autouse=True)
             def person(sqla_engine, setup_schema):
                 # Add some base data to the database here (if necessary for your application)
                 with Session(sqla_engine, expire_on_commit=False) as session:
                     person = Person(name="Test person")
                     session.add(person)
                     session.commit()
                     return person


             @pytest.fixture
             def connection(sqla_engine):
                 def restart(session, transaction):
                     nonlocal nested
                     if not nested.is_active:
                         nested = conn.begin_nested()

                 conn = sqla_engine.connect()
                 tx = conn.begin()
                 nested = conn.begin_nested()
                 event.listen(Session, "after_transaction_end", restart)

                 yield conn

                 event.remove(Session, "after_transaction_end", restart)
                 nested.rollback()
                 tx.rollback()
                 conn.close()


             @pytest.fixture
             def root_component(connection):
                 return ApplicationComponent({"sqlalchemy": {"bind": connection}})


             @pytest.fixture
             def dbsession(connection):
                 # A database session for use by testing code
                 with Session(connection) as session:
                     yield session

         .. code-tab:: python3 test_component.py

             import pytest
             from asphalt.core import Context


             @pytest.mark.asyncio
             async def test_func(root_component, dbsession):
                 """This is an actual test function which uses the database connection."""
                 async with Context() as ctx:
                     await root_component.start(ctx)
                     ...

Alternative testing plugins
---------------------------

This recipe was built with pytest-asyncio in mind, but if you're instead using AnyIO_ as
the test plugin, you should make the following changes to the async recipe:

* Drop the ``event_loop`` fixture
* Use regular ``@pytest.fixture`` to decorate the asynchronous fixtures
* Drop ``scope="session"`` from the asynchronous fixtures
* Use a global variable to record whether database initialization has been done, and
  skip the schema creation if it's been done already

.. _AnyIO: https://anyio.readthedocs.io/en/stable/
