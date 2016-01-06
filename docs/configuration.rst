Configuration
=============

A typical SQLAlchemy configuration consists of a single database engine and a session.
At minimum, you only need a connection URL (see the
:func:`SQLAlchemy documentation <sqlalchemy.create_engine>` for how to construct one).
Such a configuration would look something like this:

.. code-block:: yaml

    components:
      sqlalchemy:
        url: "postgresql://user:password@10.0.0.8/mydatabase"
        metadata: package.foo:Base.metadata

This will make the database engine accessible as ``ctx.sql`` and the ORM session as
``ctx.dbsession``.

The ``metadata`` key here is optional, but recommended. If defined, it must point to a
:class:`~sqlalchemy.schema.MetaData` object which contains information on your defined tables.
This will allow commands like :meth:`~sqlalchemy.schema.MetaData.create_all` to work.

With only a single database configured, the engine is automatically bound to the session so
commands like :meth:`~sqlalchemy.orm.session.Session.execute` will work out of the box.

.. seealso:: :meth:`asphalt.sqlalchemy.component.SQLAlchemyComponent.create_engine`
.. seealso:: :meth:`asphalt.sqlalchemy.component.SQLAlchemyComponent.create_sessionmaker`


Setting session options
-----------------------

If you need to adjust the options used for creating new sessions, you can do so by specifying them
in the ``session`` option:

.. code-block:: yaml

    components:
      sqlalchemy:
        url: "sqlite://"
        metadata: package.foo:Base.metadata
        session:
          expire_on_commit: false


Multiple databases
------------------

If you need to work with multiple databases, things get a little more complicated.
You will need to define the engines with the ``engines`` option:

.. code-block:: yaml

    components:
      sqlalchemy:
        engines:
          db1:
            url: "postgresql:///mydatabase"
            metadata: package.foo:Base.metadata
          db2:
            url: "sqlite:///mydb.sqlite"
            metadata: otherpackage.bar:Base.metadata

This will make the two database engines available as ``ctx.db1`` and ``ctx.db2`` respectively.
The session will remain available as ``ctx.dbsession``.

As you now have more than one engine, the ORM session will no longer have an engine bound to it so
:meth:`~sqlalchemy.orm.session.Session.execute` will no longer work, unless you supply an engine
as the ``bind`` keyword argument.
