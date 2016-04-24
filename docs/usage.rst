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
asyncio_extras_ library provides several alternatives for elegantly wrapping your code so it
automatically runs in a worker thread.

.. seealso:: :doc:`asphalt:userguide/concurrency`

.. _asyncio_extras: https://github.com/agronholm/asyncio_extras

Working with the Object Relational Mapper (ORM)
-----------------------------------------------

If you're not familiar with SQLAlchemy's ORM, you should look through the
`Object Relational Tutorial`_ first.

The following example code retrieves a parent ``Person`` (an arbitrarily named model class) and
adds a child to it. It makes the following assumptions:

* SQLAlchemy component configured with the default settings and one engine
* There is already a person with the name "Senior" in the database

Your codebase should contain a mapped class named ``Person``::

    from sqlalchemy.ext.declarative import declarative_base

    Base = declarative_base()


    class Person(Base):
        __tablename__ = 'people'
        id = Column(Integer, primary_key=True)
        parent_id = Column(ForeignKey('people.id'))
        name = Column(Unicode, nullable=False)

        children = relationship('Person', remote_side=[parent_id])

Then, your business logic should work along these lines::

    from asyncio_extras import threadpool


    async def handler(ctx):
        # Database queries can block the event loop, so run this in a thread pool
        async with threadpool():
            parent = ctx.dbsession.query(Person).filter_by(name='Senior').one()
            # No need to add the child to the session; cascade from the parent will trigger the INSERT
            parent.children.append(Person(name='Junior'))
            # Commit happens automatically when the context finishes

When the context finishes, the session will be automatically committed unless the context finished
due to an unhandled exception or the session is in a state of a broken transaction. This allows
you to eliminate most boilerplate ``commit()`` calls from your business logic.

.. _Object Relational Tutorial: http://docs.sqlalchemy.org/en/latest/orm/tutorial.html

Working with core queries
-------------------------

If you're not familiar with SQLAlchemy's core functionality, you should take a look at the
`SQL Expression Language Tutorial`_ first.

Here's how the above example would work using core queries::

    async def handler(ctx):
        async with threadpool():
            with ctx.sql.begin():  # optional; creates a transaction
                parent_id = ctx.sql.execute(select([people.c.id]).where(name='Senior')).scalar()
                ctx.sql.execute(people.insert().values(name='Junior'))

.. _SQL Expression Language Tutorial: http://docs.sqlalchemy.org/en/latest/core/tutorial.html
