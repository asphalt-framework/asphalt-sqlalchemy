Testing with asphalt-sqlalchemy
===============================

Testing database using code usually involves one of two approaches: either you mock your database
connections and return fake data, or you test against a real database engine. This document focuses
on the latter approach and provides instructions for setting up your fixtures accordingly.

The basic idea is to have a session level fixture which creates and engine and then makes a single
connection, through which all the database interaction will happen during the testing session.
It should first remove any previously created tables and then create the tables from scratch, using
the current metadata. This ensures that even if the testing session was interrupted previously, the
correct set of tables are always properly created. Then, during every test a transaction is started
and then rolled back after the tests, thus ensuring test isolation.

In order to force all database interactions to happen within the same transaction, the
``sqlalchemy`` component is passed the :class:`~sqlalchemy.engine.Connection` instance created by
the connection fixture as the ``bind`` option. This will override any ``url`` option passed to the
component. When the session's ``bind`` is a :class:`~sqlalchemy.engine.Connection` and not an
:class:`~sqlalchemy.engine.Engine`, it will not attempt to actually commit the transaction.
However, special measures must be taken if the application code ever rolls back the transaction.
Unlike ``commit()``, a ``rollback()`` call from a session does end the underlying transaction.
To counter that, a session listener must be set up which restarts the transaction immediately after
a session rolls it back.

This technique is based on a chapter of `SQLAlchemy documentation`_ dealing with testing.

.. note:: Always test against the same kind of database(s) as you're deploying on!
    Otherwise you may see unwarranted errors, or worse, passing tests that should have failed.

Setting up the SQLAlchemy component and the database connection
---------------------------------------------------------------

This assumes the following:

* You are using `py.test`_ for testing
* You have the necessary testing dependencies installed (``pytest``, ``pytest-asyncio``)
* You have a package ``yourapp.models`` and a declarative base class (``Base``) in it
* You have model class named ``Person`` in ``yourapp.models``
* You have a test database accessible (not required with SQLite)
* You have a project subdirectory for tests (named ``tests`` here)

The following fixtures should go in the ``conftest.py`` file in your ``tests`` folder.
They ensure that any changes made to the database are rolled back at the end of each test.

See the ``tests/test_testing_recipe`` module in the source code for a more complete example.

.. code-block:: python3

    from contextlib import closing

    import pytest
    from asphalt.core import ContainerComponent, Context
    from asphalt.sqlalchemy import clear_database
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import Session

    from yourapp.component import ApplicationComponent
    from yourapp.models import Base, Person


    @pytest.fixture(scope='session')
    def connection():
        # NOTE: SQLite requires the following argument:
        # connect_args=dict(check_same_thread=False)
        engine = create_engine('mysql://user:password@localhost/test')
        conn = engine.connect()

        # Remove existing tables and create new ones based on the current metadata
        clear_database(conn)
        Base.metadata.create_all(conn, checkfirst=False)

        yield conn

        conn.close()
        engine.dispose()


    @pytest.fixture(scope='session', autouse=True)
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
            # When any session rolls back its transaction, restart this one if it's the one that
            # has been rolled back
            nonlocal tx
            if not connection.in_transaction():
                tx = connection.begin()

        tx = connection.begin()
        event.listen(Session, 'after_rollback', restart)
        yield
        event.remove(Session, 'after_rollback', restart)
        tx.rollback()


    @pytest.fixture
    def root_context():
        with Context() as ctx:
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


.. _py.test: http://pytest.org
.. _SQLAlchemy documentation: http://docs.sqlalchemy.org/en/latest/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites
