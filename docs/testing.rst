Testing with asphalt-sqlalchemy
===============================

Testing database using code usually involves one of two approaches: either you mock your database
connections and return fake data, or you test against a real database engine. This document focuses
on the latter approach and provides instructions for setting up your fixtures accordingly.

.. note:: Always test against the same kind of database(s) as you're deploying on!
    Otherwise you may see unwarranted errors, or worse, passing tests that should have failed.

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

    from yourapp.component import ApplicationComponent
    from yourapp.models import Base, Person


    @pytest.fixture(scope='session')
    def root_context(event_loop):
        # This is the top level context that remains open throughout the testing session
        with Context() as root_ctx:
            yield root_ctx


    @pytest.fixture(scope='session')
    def root_component(event_loop, root_context):
        # Use StaticPool to guarantee that all database operations run within the same connection
        # that we start the transaction in (in the "context" fixture)
        config = {
            'sqlalchemy': {'url': 'postgresql:///yourdbname', 'poolclass': StaticPool}
        }
        root = ApplicationComponent(**config)
        event_loop.run_until_complete(root.start(root_context))


    @pytest.fixture(scope='session', autouse=True)
    def database_schema(event_loop, root_component, root_context):
        # Run all database operations in a short lived context!
        with Context(root_context) as ctx:
            # Remove tables and views left over from any previous testing session
            clear_database(ctx.sql.bind)

            # Create the current tables
            Base.metadata.create_all(ctx.sql.bind)

            # Add some base data to the database here (if necessary for your application)
            ctx.sql.add(Person(name='Test person'))


    @pytest.fixture
    def context(root_context):
        # This is the test level context, created separately for each test
        # Test functions should inject this fixture and not root_context
        with Context(root_context) as ctx:
            # Make sure that no data sent to the database during the tests is ever persisted
            connection = context.sql.bind.begin()
            yield ctx
            connection.transaction.close()

.. _py.test: http://pytest.org
