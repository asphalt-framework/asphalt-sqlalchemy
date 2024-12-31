Configuration
=============

.. highlight:: yaml

A typical SQLAlchemy configuration consists of a single database.
At minimum, you only need a connection URL (see the
:doc:`SQLAlchemy documentation <sqlalchemy:tutorial/engine>` on how to construct one).
Such a configuration would look something like this::

    components:
      sqlalchemy:
        url: postgresql+psycopg://user:password@10.0.0.8/mydatabase

This will add two static resources and one resource factory, as follows:

* engine (type: :class:`sqlalchemy.engine.Engine` or
  :class:`sqlalchemy.ext.asyncio.AsyncEngine`)
* sessionmaker (type: :class:`sqlalchemy.orm.sessionmaker`)
* session factory (generates :class:`~sqlalchemy.orm.Session` or
  :class:`sqlalchemy.ext.asyncio.AsyncSession` resources)

You can also pass the URL in separate pieces (e.g. to take advantage of YAML key/value
sharing features)::

    components:
      sqlalchemy:
        url:
          drivername: postgresql+psycopg
          username: user
          password: password
          host: 10.0.0.8
          database: mydatabase

.. seealso::
  * :class:`sqlalchemy.engine.URL`
  * :class:`asphalt.sqlalchemy.SQLAlchemyComponent`

Setting engine or session options
---------------------------------

If you need to adjust the options used for creating new sessions, or pass extra
arguments to the engine, you can do so by specifying them in the ``session_args`` and
``engine_args``, respectively::

    components:
      sqlalchemy:
        url: sqlite+aiosqlite:///:memory:
        engine_args:
          encoding: latin1
        session_args:
          info:
            hello: world
