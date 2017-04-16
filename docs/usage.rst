Using engines and sessions
==========================

SQLAlchemy, by its nature, operates in a blocking manner. That is, running a query against the
database will block the event loop. This includes implicit queries triggered by accessing lazily
loaded relationships and deferred columns.

While simple queries usually complete in a timely manner, it is often difficult to predict the
performance of interactions with such blocking APIs. The database server might be slow or
completely unreachable, in which case your whole application hangs during the query. Even when it
does not, your queries might gradually get slower due to increasing amounts of data. For these
reasons, it is recommended that you handle your SQLAlchemy interactions in worker threads. The
:class:`~asphalt.core.context.Context` class provides a few conveniences for this purpose.

.. seealso:: :doc:`asphalt:userguide/concurrency`

Transactions
------------

In asphalt-sqlalchemy, database connections are made on demand when you request a connection,
either via one of the methods in the :class:`~asphalt.core.context.Context` class or by directly
accessing the appropriate context attribute of the connection resource. The resulting connection
begins a transaction that is automatically committed when the context is was created through is
torn down, unless the context was ended by an unhandled exception. The connection is always closed
in either case.

Working with core queries
-------------------------

If you're not familiar with SQLAlchemy's core functionality, you should take a look at the
`SQL Expression Language Tutorial`_ first.

Here's how the above example would work using core queries::

    async def handler(ctx):
        # Database queries can block the event loop, so run this in a thread pool
        async with ctx.threadpool():
            parent_id = ctx.sql.scalar(select([people.c.id]).where(name='Senior'))
            ctx.sql.execute(people.insert().values(name='Junior'))

        # Commit happens automatically when the context is torn down

.. _SQL Expression Language Tutorial: http://docs.sqlalchemy.org/en/latest/core/tutorial.html

Working with the Object Relational Mapper (ORM)
-----------------------------------------------

If you're not familiar with SQLAlchemy's ORM, you should look through the
`Object Relational Tutorial`_ first.

The previous example would look like this, rewritten for the ORM::

    async def handler(ctx):
        async with ctx.threadpool():
            parent = ctx.sql.query(Person).filter_by(name='Senior').one()
            parent.children.append(Person(name='Junior'))

.. _Object Relational Tutorial: http://docs.sqlalchemy.org/en/latest/orm/tutorial.html

Loading data at application startup
-----------------------------------

It is unadvisable to use connection or session resources from a long lived context. This would
unnecessarily tie up connection resources, and if the connection is used repeatedly, it may get
stale data due to transaction isolation.

A better way is to create a throwaway child context when you need to load initial data for the
application::

    class ApplicationComponent(ContainerComponent):
        async def start(ctx):
            # ctx here is the root context
            async with Context(ctx) as subctx:
                self.employees = subctx.sql.query(Employee).all()

The connection and session will be automatically closed once the context manager block is exited.
