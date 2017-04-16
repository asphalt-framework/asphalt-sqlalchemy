Tips and tricks
===============

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
