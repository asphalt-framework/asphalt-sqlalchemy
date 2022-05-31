Configuration
=============

.. highlight:: yaml

A typical SQLAlchemy configuration consists of a single database.
At minimum, you only need a connection URL (see the
`SQLAlchemy documentation`_ for how to construct one). Such a configuration would look
something like this::

    components:
      sqlalchemy:
        url: postgresql+asyncpg://user:password@10.0.0.8/mydatabase

This will add two static resources and one resource factory, as follows:

* engine (type: :class:`sqlalchemy.future.engine.Engine` or
  :class:`sqlalchemy.ext.asyncio.AsyncEngine`)
* sessionmaker (type: :class:`sqlalchemy.orm.sessionmaker`)
* session factory (generates :class:`~sqlalchemy.orm.Session` or
  :class:`sqlalchemy.ext.asyncio.AsyncSession` resources)

You can also pass the URL in separate pieces (e.g. to take advantage of YAML key/value
sharing features)::

    components:
      sqlalchemy:
        url:
          drivername: postgresql+asyncpg
          username: user
          password: password
          host: 10.0.0.8
          database: mydatabase

.. seealso::
  * :class:`sqlalchemy.engine.URL`
  * :class:`asphalt.sqlalchemy.component.SQLAlchemyComponent`

.. _SQLAlchemy documentation: https://docs.sqlalchemy.org/en/14/core/engines.html

Setting engine or session options
---------------------------------

If you need to adjust the options used for creating new sessions, or pass extra
arguments to the engine, you can do so by specifying them in the ``session`` option::

    components:
      sqlalchemy:
        url: sqlite+aiosqlite:///:memory:
        engine_args:
          encoding: latin1
        session_args:
          info:
            hello: world

Multiple databases
------------------

If you need to work with multiple databases, you will need to use multiple instances
of the ``sqlalchemy`` component::

    components:
      sqlalchemy:
        resource_name: db1
        url: postgresql+asyncpg:///mydatabase
      sqlalchemy2:
        type: sqlalchemy
        resource_name: db2
        url: sqlite+aiosqlite:///mydb.sqlite

The will make the appropriate resources available using their respective namespaces
(``db1`` or ``db2`` instead of ``default``).
