Testing with asphalt-sqlalchemy
===============================

Testing database using code usually involves one of two approaches: either you mock your
database connections and return fake data, or you test against a real database engine.
This document focuses on the latter approach and provides instructions for setting up
your fixtures accordingly.

The basic idea is to have a session level fixture which creates and engine and then
makes a single connection, through which all the database interaction will happen during
the testing session. Unless you're running SQLite, PostgreSQL or another RDBMS that
supports transactional DDL, the fixture should first remove any previously created'
tables. This ensures that even if the testing session was interrupted previously, the
correct set of tables are always properly created. On back-ends where transactional DDL
is supported, rolling back the session scoped connection's transaction will also roll
back the ``CREATE TABLE`` commands, making the database look empty to any other clients,
including subsequent (or parallel) test sessions.

Next, it should create the tables from scratch, using the current metadata. Then, a
test-scoped, autouse fixture should create savepoint in the connection. After the test,
that savepoint should be restored to ensure test isolation.

In order to force all database interactions to happen within the same transaction, the
``sqlalchemy`` component is passed the connection object created by the connection
fixture as the ``bind`` option. This will override any ``url`` option passed to the
component. When a session sees that its connection is part of an externally managed
transaction, it will not try to actually commit it.

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

            from yourapp.component import ApplicationComponent
            from yourapp.models import Base, Person


            @pytest.fixture(scope="session")
            def event_loop():
                # Required for session scoped async fixtures; only works with pytest-asyncio
                loop = new_event_loop()
                set_event_loop(loop)
                yield loop
                loop.close()


            @pytest_asyncio.fixture(scope="session")
            async def connection():
                # For SQLite, some additional hacks are required:
                #
                # from asphalt.sqlalchemy.utils import apply_sqlite_hacks
                # engine = create_engine("sqlite+aiosqlite:///:memory:")
                # apply_sqlite_hacks(engine)

                engine = create_engine("postgresql+asyncpg://user:password@localhost/test")
                async with engine.connect() as conn:
                    # Clear out previous tables (optional on sqlite, PostgreSQL,
                    # possibly others too where transactional DDL is supported)
                    await clear_async_database(conn)
                    await conn.run_sync(Base.metadata.create_all, checkfirst=False)
                    yield conn

                await engine.dispose()


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
            def connection():
                # For SQLite, some additional hacks are required:
                #
                # from asphalt.sqlalchemy.utils import apply_sqlite_hacks
                # engine = create_engine(
                #     "sqlite:///:memory:",
                #     connect_args={"check_same_thread": False}
                # )
                # apply_sqlite_hacks(engine)

                engine = create_engine("postgresql+psycopg2://user:password@localhost/test")
                with engine.connect() as conn:
                    # Clear out previous tables (optional on sqlite, PostgreSQL,
                    # possibly others too where transactional DDL is supported)
                    clear_database(conn)
                    Base.metadata.create_all(conn, checkfirst=False)
                    yield conn


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

Adding base data
----------------

It's often useful to add base data to the database that is used by several tests or
fixtures. This can be done on all scopes provided by pytest: ``session``, ``package``,
``module``, ``class`` or ``function``. The basic idea is to create a **save point**, add
your data, and then in the teardown stage, roll back to the save point. This technique
allows multiple data fixtures from multiple scopes to coexist:

.. tabs::

   .. code-tab:: python3 Asynchronous

       @pytest_asyncio.fixture(scope="session", autouse=True)
       def session_base_data(connection):
           tx = await connection.begin_nested()
           async with AsyncSession(connection, expire_on_commit=False) as session:
               person = Person(name="Test person")
               session.add(person)
               await session.commit()

          yield person
          await tx.rollback()


       @pytest_asyncio.fixture(scope="module", autouse=True)
       def module_base_data(connection):
           tx = await connection.begin_nested()
           async with AsyncSession(connection, expire_on_commit=False) as session:
               person = Person(name="Another test person")
               session.add(person)
               await session.commit()

          yield person
          await tx.rollback()

   .. code-tab:: python3 Synchronous

       @pytest.fixture(scope="session", autouse=True)
       def session_base_data(connection):
           tx = connection.begin_nested()
           with Session(connection, expire_on_commit=False) as session:
               person = Person(name="Test person")
               session.add(person)
               session.commit()

          yield person
          tx.rollback()


       @pytest.fixture(scope="module", autouse=True)
       def module_base_data(connection):
           tx = connection.begin_nested()
           with Session(connection, expire_on_commit=False) as session:
               person = Person(name="Anothr test person")
               session.add(person)
               session.commit()

          yield person
          tx.rollback()

Using alternative async testing plugins
---------------------------------------

This recipe was built with pytest-asyncio in mind, but if you're instead using AnyIO_ as
the test plugin, you should make the following changes to the async recipe:

* Drop the ``event_loop`` fixture
* Use regular ``@pytest.fixture`` to decorate the asynchronous fixtures

.. _AnyIO: https://anyio.readthedocs.io/en/stable/
