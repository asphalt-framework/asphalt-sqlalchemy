Configuration
=============

.. highlight:: yaml

A typical SQLAlchemy configuration consists of a single database.
At minimum, you only need a connection URL (see the
:func:`SQLAlchemy documentation <sqlalchemy.create_engine>` for how to construct one).
Such a configuration would look something like this::

    components:
      sqlalchemy:
        url: "postgresql://user:password@10.0.0.8/mydatabase"

This will make the ORM session (:class:`~sqlalchemy.orm.Session`) accessible as ``ctx.sql`` and the
database engine (:class:`~sqlalchemy.engine.Engine`) as ``ctx.sql.bind``.

.. seealso:: :meth:`asphalt.sqlalchemy.component.SQLAlchemyComponent.create_engine`
.. seealso:: :meth:`asphalt.sqlalchemy.component.SQLAlchemyComponent.create_sessionmaker`

Setting session options
-----------------------

If you need to adjust the options used for creating new sessions, you can do so by specifying them
in the ``session`` option::

    components:
      sqlalchemy:
        url: "sqlite:///:memory:"
        session:
          info:
            hello: world

Multiple databases
------------------

If you need to work with multiple databases, things get a little more complicated.
You will need to define the engines with the ``engines`` option::

    components:
      sqlalchemy:
        engines:
          db1:
            url: "postgresql:///mydatabase"
          db2:
            url: "sqlite:///mydb.sqlite"

This will make the two sessions available as ``ctx.db1`` and ``ctx.db2`` respectively.
