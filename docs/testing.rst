Testing with asphalt-sqlalchemy
===============================

Testing database using code usually involves one of two approaches: either you mock your database
connections and return fake data, or you test against a real database engine. This document focuses
on the latter approach and provides instructions for setting up your fixtures accordingly.

.. note:: Always test against the same kind of database(s) as you're deploying on!
    Otherwise you may see unwarranted errors, or worse, tests that should have failed may pass.

Setting up the SQLAlchemy component and the database connection
---------------------------------------------------------------

This assumes the following:

* You are using `py.test`_ for testing
* You have the necessary testing dependencies installed (``pytest``, ``pytest-asyncio``)
* You have a package ``yourapp.models`` and a declarative base class (``Base``) in it
* You have model class named ``Person`` in ``yourapp.models``
* You have an empty database accessible (not required with SQLite)
* You have a project subdirectory for tests (named ``tests`` here)

The following fixtures should go in the ``conftest.py`` file in your ``tests`` folder.
They ensure that any changes made to the database are rolled back at the end of each test.

.. code-block:: python3

    import pytest
    from asphalt.core import ContainerComponent, Context
    from asphalt.sqlalchemy.utils import connect_test_database
    from sqlalchemy import create_engine
    from sqlalchemy.schema import MetaData, DropConstraint

    from yourapp.models import Base, Person


    @pytest.yield_fixture(scope='session')
    def connection():
        connection = connect_test_database('mysql://user:password@localhost/test'))
        Base.metadata.create_all(connection)
        yield connection
        connection.close()


    @pytest.fixture(scope='session')
    def root_component(connection):
        # The trick here is to pass the connection to the SQLAlchemy component where it will be
        # used in place of any implicitly created Engine
        root = ContainerComponent():
        root.add_component('sqlalchemy', bind=connection, metadata=Base.metadata)
        return root


    @pytest.yield_fixture(scope='session')
    def root_context(event_loop, root_component):
        # This is the top level context that remains open throughout the testing session
        context = Context()
        event_loop.run_until_complete(root_component.start(context))
        yield context
        event_loop.run_until_complete(context.finished.dispatch(None, return_future=True))


    @pytest.fixture(scope='session', autouse=True)
    def base_data(event_loop, root_context):
        # Add some base data to the database here (optional)
        root_context.dbsession.add(Person(name='Test person'))
        root_context.dbsession.flush()


    @pytest.yield_fixture(autouse=True)
    def transaction(connection):
        # Make sure that no data sent to the database during the tests is ever persisted
        transaction = connection.begin()
        yield
        transaction.rollback()


    @pytest.yield_fixture
    def context(root_context):
        # This is the test level context, created separately for each test
        # Test functions should inject this fixture and not root_context
        context = Context(root_context)
        yield context
        event_loop.run_until_complete(context.finished.dispatch(None, return_future=True))


Connection setup, alternate method
----------------------------------

If you're using an RDBMS that supports `transactional DDL`_ (such as `PostgreSQL`_), you can use a
somewhat cleaner approach that creates all the tables within a transaction and creates a savepoint
before each test and then just rolls back to the savepoint after the test. The primary advantage of
this approach is slightly better performance.

Assuming the same content as in the previous example, only these two fixtures need modifications::

    @pytest.yield_fixture(scope='session')
    def connection():
        engine = create_engine('postgresql:///testdb')
        with engine.connect() as connection
            # Create the tables within a transaction
            transaction = connection.begin()
            Base.metadata.create_all(connection)

            yield connection

            # This will undo all the table creation, leaving you with an empty database
            transaction.rollback()


    @pytest.yield_fixture(autouse=True)
    def transaction(connection):
        # This will create a savepoint within the transaction that was started in the
        # "connection" fixture
        transaction = connection.begin_nested()

        yield

        # This will roll the transaction back to the previously created savepoint
        transaction.rollback()


.. _py.test: http://pytest.org
.. _PostgreSQL: http://www.postgresql.org/
