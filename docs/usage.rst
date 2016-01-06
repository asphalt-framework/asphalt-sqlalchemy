Using engines and sessions
==========================

Asphalt-sqlalchemy provides enhanced versions of SQLAlchemy's
:class:`~sqlalchemy.engine.Engine`, :class:`~sqlalchemy.engine.Connection`,
:class:`~sqlalchemy.orm.session.Session` and :class:`~sqlalchemy.orm.query.Query`
classes, modified to make them work better with asyncio by wrapping all methods that would
potentially block the event loop for long periods of time.

Additionally, some support is provided to make the ORM session more convenient to use by providing
context manager (regular and asynchronous) support in the
:class:`~asphalt.sqlalchemy.async.AsyncSession` class.


Working with a Session
----------------------

If you're not familiar with SQLAlchemy's ORM, it is recommended that you look through the
`Object Relational Tutorial`_ first.

The following example code retrieves a parent ``Person`` (an arbitrarily named model class) and
adds a child to it. It makes the following assumptions:

* SQLAlchemy component configured with the default settings and one engine
* There is already a person with the name "Senior" in the database

The models module should contain the Person class:

.. code-block:: python

    from sqlalchemy.ext.declarative import declarative_base

    Base = declarative_base()


    class Person(Base):
        __tablename__ = 'people'
        id = Column(Integer, primary_key=True)
        parent_id = Column(ForeignKey('people.id'))
        name = Column(Unicode, nullable=False)

        children = relationship('Person', remote_side=[parent_id])

Then, your business logic should work along these lines:

.. code-block:: python

    @blocking
    def handler(ctx):
        with ctx.dbsession:
            parent = ctx.dbsession.query(Person).filter_by(name='Senior').one()
            # No need to add the child to the session; cascade from the parent will trigger the INSERT
            parent.children.append(Person(name='Junior'))
            # The context manager commits the session on exit

The context manager will automatically commit the session unless the block was exited due to an
exception being raised.

The above example using a native coroutine handler would look like this:

.. code-block:: python

    async def handler(ctx):
        async with ctx.dbsession:
            parent = await ctx.dbsession.query(Person).filter_by(name='Senior').one()
            parent.children.append(Person(name='Junior'))
            # The context manager commits the session on exit

In a non-native (Python 3.4) coroutine this requires a tad more code as the async context manager
can't be used:

.. code-block:: python

    from contextlib import closing

    @coroutine
    def handler(ctx):
        with closing(ctx.dbsession):
            parent = yield from ctx.dbsession.query(Person).filter_by(name='Senior').one()
            parent.children.append(Person(name='Junior'))
            yield from ctx.dbsession.commit()

.. _Object Relational Tutorial: http://docs.sqlalchemy.org/en/latest/orm/tutorial.html


ORM gotchas and pitfalls with asynchronous code
-----------------------------------------------

By its nature, SQLAlchemy is not very friendly to the explicit asynchronous programming style.
In particular, there are two features of the ORM that are problematic and will only work with
``@blocking``:

* Iteration over a :class:`~sqlalchemy.orm.query.Query`
* Lazy loading of related objects and collections

Attempting to use these features from the event loop thread will cause confusing exceptions because
the necessary methods have been wrapped with ``@blocking`` which makes them work as coroutines
from the event loop thread and the SQLAlchemy API is not expecting that.

It should also be noted that ORM sessions are *not* safe to use concurrently in multiple threads
or even in multiple asyncio tasks. Therefore, **never** attempt to spawn multiple tasks that share
the same :class:`~sqlalchemy.orm.session.Session`. However, if you run each task in their own
:class:`~asphalt.core.context.Context`, they will automatically get their own Session instance
which solves the problem.


Session automatic commit at the end of the context
--------------------------------------------------

When a :class:`~asphalt.core.context.Context` containing an ORM session is finished, the session
is automatically committed unless the context ended with an exception. If the context is a short
lived one, like a request context in an RPC or web server, this saves you from explicitly using
the context manager feature of :class:`~asphalt.sqlalchemy.async.AsyncSession`:

.. code-block:: python

    @blocking
    def handler(ctx):
        parent = ctx.dbsession.query(Person).filter_by(name='Senior').one()
        # No need to add the child to the session; cascade from the parent will trigger the INSERT
        parent.children.append(Person(name='Junior'))
        # Commit is done automatically at the end of the context


Working with core queries
-------------------------

If you're not familiar with SQLAlchemy's core functionality, you should take a look at the
`SQL Expression Language Tutorial`_ first.

The above example can also be done using core queries:

.. code-block:: python

    @blocking
    def handler(ctx):
        with ctx.sql.begin():  # optional; creates a transaction
            parent_id = ctx.sql.execute(select([people.c.id]).where(name='Senior')).scalar()
            ctx.sql.execute(people.insert().values(name='Junior'))

.. _SQL Expression Language Tutorial: http://docs.sqlalchemy.org/en/latest/core/tutorial.html
