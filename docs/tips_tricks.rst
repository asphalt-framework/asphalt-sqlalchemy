Tips and tricks
===============

Here you will find help on performing some common tasks related to SQLAlchemy with
Asphalt.

How to automatically print emitted SQL
--------------------------------------

This can be done in one of two ways:

#. Add the ``echo=True`` option to the engine configuration options
#. In your application's configuration, add a logger for ``sqlalchemy.engine.base``:

.. code-block:: yaml

    logging:
      root:
        handlers: [console]
        level: WARNING
      loggers:
        asphalt:
          level: INFO
        sqlalchemy.engine:
          level: INFO

.. seealso:: https://docs.sqlalchemy.org/en/14/core/engines.html#dbengine-logging

Handling schema migrations
--------------------------

For schema migrations, it is best to use the Alembic_ tool, which is made by
SQLAlchemy's author.

The tool should not be used from the application itself though, but instead run
during your upgrade procedure before your new code has a chance to run. And as a
reminder, if your application must not have downtime, the schema upgrade should be
backwards compatible with the previous version.

.. _Alembic: https://alembic.zzzcomputing.com/en/latest/
