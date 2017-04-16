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
    from asphalt.sqlalchemy.utils import clear_database

    from yourapp.models import Base, Person


    @pytest.fixture(scope='session')
    def root_component():
        root = ContainerComponent()
        root.add_component('sqlalchemy')
        return root


    @pytest.fixture(scope='session')
    def root_context(event_loop, root_component):
        # This is the top level context that remains open throughout the testing session
        with Context() as root_ctx:
            # Run all database operations in a short lived context!
            with Context(root_ctx) as ctx:
                # Remove tables and views left over from any previous testing session
                clear_database(ctx.sql.bind)

                # Create the current tables
                Base.metadata.create_all(ctx.sql.bind)

                # Add some base data to the database here (if necessary for your application)
                ctx.sql.add(Person(name='Test person'))

            # When you "yield" inside a with: block, the block won't end until the yield returns
            yield context


    @pytest.fixture
    def context(root_context):
        # This is the test level context, created separately for each test
        # Test functions should inject this fixture and not root_context
        with Context(root_context) as ctx:
            yield ctx


    @pytest.fixture(autouse=True)
    def transaction(context):
        # Make sure that no data sent to the database during the tests is ever persisted
        transaction = context.sql.begin()
        yield
        transaction.rollback()


Connection setup, alternate method
----------------------------------

If you're using an RDBMS that supports `transactional DDL`_ (such as `PostgreSQL`_), you can use a
somewhat cleaner approach that creates all the tables within a transaction and creates a savepoint
before each test and then just rolls back to the savepoint after the test. The primary advantage of
this approach is slightly better performance.

Assuming the same content as in the previous example, only these two fixtures need modifications::

    @pytest.fixture(scope='session')
    def connection():
        engine = create_engine('postgresql:///testdb')
        with engine.connect() as connection
            # Create the tables within a transaction
            transaction = connection.begin()
            Base.metadata.create_all(connection)

            yield connection

            # This will undo all the table creation, leaving you with an empty database
            transaction.rollback()


.. _py.test: http://pytest.org
.. _transactional DDL: https://wiki.postgresql.org/wiki/Transactional_DDL_in_PostgreSQL:_A_Competitive_Analysis
.. _PostgreSQL: http://www.postgresql.org/
