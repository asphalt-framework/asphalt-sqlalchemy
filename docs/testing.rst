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

.. code-block:: python

    from sqlalchemy import create_engine
    from sqlalchemy.schema import MetaData, DropConstraint
    from asphalt.core.component import ContainerComponent
    from asphalt.core.context import Context
    from asphalt.sqlalchemy.utils import connect_test_database
    import pytest

    pytest_plugins = ['asphalt.core.pytest_plugin']


    @pytest.yield_fixture(scope='session')
    def connection():
        from yourapp.models import Base

        # Make a connection to the test database
        connection = connect_test_database('mysql://user:password@localhost/testdb')

        # Create the tables
        Base.metadata.create_all(connection)

        yield connection

        connection.close()


    @pytest.fixture(scope='session')
    def top_component(connection):
        # This is where you set up your top level component.
        # Naturally, it will include the SQLAlchemy component, but instead of a connection URL
        # you will give it the connection object as the "bind" argument.
        return ContainerComponent({
            'sqlalchemy': {'bind': connection, 'metadata': Base.metadata}
        })


    @pytest.yield_fixture(scope='session')
    def top_context(event_loop, top_component):
        # This is the top level context that remains open throughout the testing session
        with Context() as context:
            # This will start all the components in the hierarchy, just as the runner would do
            event_loop.run_until_complete(top_component.start(context))
            yield context


    @pytest.fixture(scope='session', autouse=True)
    def base_data(event_loop, top_context):
        from yourapp.models import Person

        # Add some base data to the database here (optional)
        top_context.dbsession.add(Person(name='Test person'))
        event_loop.run_until_complete(top_context.dbsession.flush())


    @pytest.yield_fixture(autouse=True)
    def transaction(connection):
        # Make sure that no data sent to the database during the tests is ever persisted
        transaction = connection.begin()
        yield
        transaction.rollback()


    @pytest.yield_fixture
    def context(top_context):
        # This is the test level context, created separately for each test
        with Context(top_context) as context:
            yield context


Connection setup, alternate method
----------------------------------

If you're using an advanced RDBMS, such as `PostgreSQL`_, that supports savepoints
(``CREATE SAVEPOINT``) and transactional DDL, you can use a somewhat cleaner approach that creates
all the tables within a transaction and runs all the tests inside a nested transaction.
The primary advantage of this approach is slightly better performance.

.. code-block:: python

    # Assume the same content as in the previous example, except for these two fixtures

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
