Using engines and sessions
==========================

Most of the time, developers will use the provided SQLAlchemy sessions (sync or async)
and won't be interested in the other provided resources, except in some special
circumstances. The SQLAlchemy component's session resource factory manages these
sessions in such a way that any open transaction is committed when the context ends,
unless an unhandled exception causes the context to be closed, in which case the
transaction will be rolled back. All connection resources are released when the context
closes either way.

Working with the SQLAlchemy session
-----------------------------------

If you're not familiar with SQLAlchemy's sessions, you should look through the
`SQLAlchemy session documentation`_ first.

A basic use case which loads a specific person record from the database and adds a
new related object to it would look like this::

    from asphalt.core import inject, resource
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.future import select

    from yourapp.model import Person


    @inject
    async def handler(*, dbsession: AsyncSession = resource()) -> None:
        parent = await dbsession.scalar(select(Person).filter_by(name='Senior'))
        parent.children.append(Person(name='Junior'))
        await dbsession.flush()

The flush operation at the end causes the ``INSERT`` command to be emitted, but does not
commit the transaction. The transaction is committed when the context ends successfully.
You can of course call ``dbsession.commit()`` instead of ``dbsession.flush()`` to commit
the transaction then and there.

.. _SQLAlchemy session documentation: https://docs.sqlalchemy.org/en/14/orm/session.html

Working with synchronous sessions
---------------------------------

If you're fortunate enough to be able to use an asynchronous engine for your use case,
you can skip this section. For those having to use engines for which no async
counterpart is available, read on.

Synchronous database connections in an asynchronous application pose a problem because
running operations against a database will block the event loop, and thus need to be
wrapped in worker threads. Another thing to watch out for is lazy loading of
relationships and deferred columns which triggers implicit queries when those attributes
are accessed.

On Python 3.9 and above, you would do::

    from asyncio import to_thread

    from asphalt.core import inject, resource
    from sqlalchemy.orm import Session
    from sqlalchemy.future import select

    from yourapp.model import Person


    @inject
    async def handler(*, dbsession: Session = resource()) -> None:
        people = await to_thread(dbsession.scalars, select(Person))


On earlier Python versions::

    from asyncio import get_running_loop

    from asphalt.core import inject, resource
    from sqlalchemy.orm import Session
    from sqlalchemy.future import select

    from yourapp.model import Person


    @inject
    async def handler(*, dbsession: Session = resource()) -> None:
        loop = get_running_loop()
        people = await loop.run_in_executor(None, dbsession.scalars, select(Person))

Releasing database resources during a long operation
----------------------------------------------------

If you are running a long operation and you're unnecessarily holding onto a database
connection (if, say, you needed data from the database to start the operation, you can
release those resources by closing the session after the initial use::

    from asphalt.core import inject, resource
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.future import select

    from yourapp.model import Person


    @inject
    async def work_task(*, dbsession: AsyncSession = resource()) -> None:
        person = await dbsession.scalar(select(Person).limit(1))
        await dbsession.close()
        ...  # work with the data
        dbsession.add(some_object)
        await dbsession.flush()

The session will reacquire a connection when it needs to perform a database operation.
