Testing with asphalt-sqlalchemy
===============================



.. note:: Always test against the same kind of database(s) as you're deploying on!

Setting up the test fixtures
----------------------------

This assumes the following:

* You have the necessary testing dependencies installed (``pytest``, ``pytest-asyncio``)
* You have a package ``yourapp.models`` and a declarative base class (``Base``) in it
* You have model class named ``Person`` in ``yourapp.models``
* You have an empty database accessible (not required with SQLite)
* You have a project subdirectory for tests (named ``tests`` here)

The following fixtures should go in ``tests/conftest.py``.
The name ``conftest.py`` has special meaning to py.test and must not be changed.

Connection setup, alternate method
**********************************

This method relies on nested transactions (``CREATE SAVEPOINT``) and transactional DDL and thus
requires an advanced RDBMS such as PostgreSQL. It creates the tables within a transaction and then
creates a savepoint at the start of each test and then rolls back to the savepoint when the test
has finished.

.. code-block:: python

    from sqlalchemy import create_engine
    from asphalt.sqlalchemy.component import SQLAlchemyComponent
    import pytest

    from yourapp.models import Base, Person


    @pytest.yield_fixture(scope='session')
    def connection():
        # Create the engine
        engine = create_engine('postgresql:///testdb')

        # Connect to the database and start a transaction
        with engine.connect() as connection, connection.begin() as transaction
            metadata.create_all(connection)  # Create the tables
            yield connection
            transaction.rollback()

        engine.dispose()


    @pytest.yield_fixture(autouse=True)
    def test_transaction(connection):
        # Make sure that any data written to the db during the tests is never persisted
        transaction = connection.begin_nested()
        yield transaction
        transaction.rollback()



Setting up the SQLAlchemy component and the base data
*****************************************************

.. code-block:: python

    from sqlalchemy import create_engine
    from sqlalchemy.schema import MetaData, DropConstraint
    from asphalt.sqlalchemy.component import SQLAlchemyComponent
    import pytest

    from yourapp.models import Base, Person


    @pytest.yield_fixture(scope='session')
    def connection():
        engine = create_engine('mysql://user:password@localhost/testdb')
        with engine.connect() as connection
            # Reflect the schema to get the list of tables and constraints
            metadata = MetaData(connection)
            metadata.reflect()

            # Drop all the foreign key constraints so we can drop the tables in any order
            for table in metadata.tables.values():
                for fk in table.foreign_keys:
                    connection.execute(DropConstraint(fk.constraint))

            # Drop and recreate the tables
            metadata.drop_all()
            metadata.create_all()
            yield connection

        engine.dispose()


    @pytest.fixture(scope='session')
    def application(connection):
        # This is a very barebones top level container component that uses SQLAlchemy.
        # Its only purpose is to demonstrate how the SQLAlchemy component integrates with
        # your application. Otherwise you could just return the SQLAlchemy component directly.
        # Note that it is crucial to pass the previously created connection directly
        # instead of a connection URL.
        return ContainerComponent({
            'sqlalchemy': {
                'engines': {
                    'testdb': {'bind': connection, 'metadata': Base.metadata}
                }
            }
        })


    @pytest.yield_fixture(scope='session')
    def app_context(event_loop, application):
        # This is the top level context that remains open throughout the testing session
        with Context() as context:
            yield context


    @pytest.fixture(scope='session', autouse=True)
    def base_data(app_context):
        # Add some base data to the database here
        app_context.dbsession.add(Person(name='Test person'))
        app_context.dbsession.commit()


    @pytest.yield_fixture(autouse=True)
    def test_transaction(connection):
        # Make sure that any data written to the db during the tests is never persisted
        transaction = connection.begin()
        yield transaction
        transaction.rollback()


    @pytest.yield_fixture
    def context(app_context):
        # This is the test level context, created separately for each test
        with Context(app_context) as context:
            yield context
