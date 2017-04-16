Tips and tricks
===============

Here you will find help on performing some common tasks related to SQLAlchemy with Asphalt.

How to automatically print emitted SQL
--------------------------------------

This can be done two ways:

#. Add the ``echo=True`` option to the engine configuration options
#. In your application's configuration, add a logger for ``sqlalchemy.engine.base``:

.. code-block:: yaml

    logging:
      ...
      loggers:
        root:
          handlers: [console]
          level: WARNING
        asphalt:
          level: INFO
        sqlalchemy.engine.base:
          level: INFO

Handling schema migrations
--------------------------

For schema migrations, it is best to use the Alembic_ tool, which is made by SQLAlchemy's author.
An ideal place to put your Alembic migration code in the application is the ``start()`` method of
your application component, after calling ``await super().start(ctx)``, but **before** starting any
services that might actually use the database. If this is not feasible, consider fishing the
connection URL(s) out of ``self.component_configs`` dictionary and running the migration before
calling the superclass ``start()`` method.

Assuming that you have an ``alembic`` directory in the same directory as the module containing the
application component class, here's how you might do it::

    import os

    from alembic import command, config

    class ApplicationComponent(ContainerComponent):
        async def start(self, ctx):
            await super().start(ctx)

            cfg = config.Config(os.path.dirname(__file__), 'alembic', 'alembic.ini')
            with ctx.sql.bind.begin() as connection:
                cfg.attributes['connection'] = connection
                command.upgrade(cfg, "head")

Notice the direct use of the engine here – it's okay as long as the connection created is short
lived, as is guaranteed by doing ``with engine.begin():``.

.. _Alembic: http://alembic.zzzcomputing.com/en/latest/
