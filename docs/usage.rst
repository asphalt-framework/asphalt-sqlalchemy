User guide
==========

By its nature, SQLAlchemy is not very friendly to the explicit asynchronous programming style.
In particular, iteration over a :class:`~sqlalchemy.orm.Query` and lazy loading of relationships
and deferred columns will implicitly cause further queries to be run which block the event loop.
Therefore it is strongly recommended that you make your handler run in a thread using the
:py:obj:`~asphalt.core.util.blocking` decorator when using SQLAlchemy.

That said, some augmentations to the upstream SQLAlchemy API are provided to make it work better
with event loops:

* Wrapping all blocking methods in the engine, session and query
* Providing "async with" support in the session

.. _Object Relational Tutorial: http://docs.sqlalchemy.org/en/latest/orm/tutorial.html
.. _SQL Expression Language Tutorial: http://docs.sqlalchemy.org/en/latest/core/tutorial.html


Configuration
-------------

The general structure of the configuration is as follows:

.. code-block:: yaml

    session:
      context_var: dbsession
      commit_on_finish: false
      # add any keyword arguments to sessionmaker() here
    engines:
      db1:
        url: "postgresql:///mydatabase"
        metadata: package.foo:Base.metadata
        # add any keyword arguments to create_engine() here
      db2:
        url: "sqlite:///mydb.sqlite"
        metadata: otherpackage.bar:Base.metadata
        # add any keyword arguments to create_engine() here

This example configures two database engines, named ``db1`` an ``db2``. The first connects to a
PostgreSQL database named "mydatabase" via UNIX sockets and the second connects to an SQLite
database file named ``mydb.sqlite``.

In order to use the session, you need to connect the configured engines to the metadata in your
declarative base class(es). This is done by specifying the ``metadata`` option for each engine,
as shown above.




Published resources
-------------------

The SQLAlchemy component publishes the configured engines as resources of type
:class:`asphalt.sqlalchemy.async.AsyncEngine`. Each engine resource is named the same as its
configuration key (``db1`` and ``db2`` in the above example) and they are available on the context
with the same names.

Unless you explicitly disabled the ORM by setting ``session`` to ``False``, the following
resources are also published:

* a :class:`sqlalchemy.orm.session.sessionmaker` named ``default`` (no context variable)
* an :class:`asphalt.sqlalchemy.async.AsyncSession` as a lazy resource named ``default``
  (available on the context as ``dbsession`` by default; configurable via ``context_var``)


Working with a Session
----------------------

The following example code retrieves a parent Person (an arbitrarily named model class) and adds
a child to it. It makes the following assumptions:

* SQLAlchemy component configured with the default settings and one engine named "db"
* The context (``ctx``) here is a request handler context which finishes right after this
  method call
* ``Person`` is a mapped class you've imported from elsewhere
* ``Person.children`` is a one-to-many relationship to ``Person`` itself (self referential)
* There is already a person with the name "Senior" in the database

.. code-block:: python

    @blocking
    def handler(ctx):
        with ctx.dbsession:
            parent = ctx.dbsession.query(Person).filter_by(name='Senior').one()
            # No need to add the child to the session; cascade from the parent will trigger the INSERT
            parent.children.append(Person(name='Junior'))
            # No need for explicit .commit() since commit_on_finish is enabled by default

The above example using a coroutine handler would look like this in Python 3.5 and above:

.. code-block:: python

    async def handler(ctx):
        async with ctx.dbsession:
            parent = await ctx.dbsession.query(Person).filter_by(name='Senior').one()
            parent.children.append(Person(name='Junior'))

In a Python 3.4 coroutine it gets a little awkward as the async context manager can't be used:

.. code-block:: python

    @coroutine
    def handler(ctx):
        try:
            parent = yield from ctx.dbsession.query(Person).filter_by(name='Senior').one()
            parent.children.append(Person(name='Junior'))
            yield from ctx.dbsession.commit()
        finally:
            ctx.dbsession.close()


Using Session in short-lived contexts
-------------------------------------

Request serving Components typically create short lived "request" contexts for the request handlers
which finish right after the handler function has finished executing.
In such cases it is possible to further simplify the use of the Session by skipping the use of the
context manager:

.. code-block:: python

    @blocking
    def handler(ctx):
        parent = ctx.dbsession.query(Person).filter_by(name='Senior').one()
        # No need to add the child to the session; cascade from the parent will trigger the INSERT
        parent.children.append(Person(name='Junior'))
        # No need for explicit .commit() since commit_on_finish is enabled by default

Async style in Python 3.5+:

.. code-block:: python

    async def handler(ctx):
        parent = await ctx.dbsession.query(Person).filter_by(name='Senior').one()
        parent.children.append(Person(name='Junior'))

And Python 3.4:

.. code-block:: python

    @coroutine
    def handler(ctx):
        parent = yield from ctx.dbsession.query(Person).filter_by(name='Senior').one()
        parent.children.append(Person(name='Junior'))


Working with core queries
-------------------------

