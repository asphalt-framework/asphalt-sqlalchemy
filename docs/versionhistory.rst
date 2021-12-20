Version history
===============

This library adheres to `Semantic Versioning <http://semver.org/>`_.

**3.2.0** (2021-12-20)

- Added support for Python 3.10
- Dropped support for Python 3.5 and 3.6
- Fixed deprecation warning about initializing SQLAlchemy ``URL`` objects directly

**3.1.4** (2019-01-16)

- Eliminated the possibility of ``session.commit()`` and ``session.close()`` being called
  concurrently

**3.1.3** (2018-12-18)

- Implemented better mechanics for exception handling to make sure that ``session.close()`` is
  always executed

**3.1.2** (2018-12-11)

- Shield ``session.close()`` from cancellation to ensure that the connection is returned to the
  pool

**3.1.1** (2018-10-01)

- Execute ``session.close()`` in a worker thread, as it can potentially block the event loop thread

**3.1.0** (2017-07-08)

- Allowed the ``engine`` argument to ``clear_database()`` to be any ``Connectable``
- Added the ``ready_callback`` option to engine configuration (should be handy for creating tables
  or doing schema migrations)
- Restored the ability to pass a ``Connection`` as the ``bind`` configuration option
- Made the ``poolclass`` engine option passable as a ``module:varname`` reference
  (contributed by Devin Fee)
- Improved the testing recipe and added tests for it
- Added compatibility with Asphalt 4.0

**3.0.1** (2017-05-06)

- Fixed ``clear_database()`` causing an SQLAlchemy error when ``metadata.drop_all()`` tries to drop
  constraints that ``clear_database()`` has already dropped
- Sped up ``clear_database()`` a bit by not checking for the presence of tables when dropping them
  right after reflecting the metadata

**3.0.0** (2017-04-16)

- **BACKWARD INCOMPATIBLE** Migrated to Asphalt 3.0
- **BACKWARD INCOMPATIBLE** Engine resources are no longer directly accessible as context
  variables. Instead, every engine gets its own session and can be accessed via the session's
  ``bind`` variable.
- **BACKWARD INCOMPATIBLE** The component now longer accepts bare ``Connection`` objects to be
  added as resources
- **BACKWARD INCOMPATIBLE** The commit executor is now configured on the component level
- An explicit commit executor is now always used (a new one will be created implicitly if none is
  defined in the configuration)
- **BACKWARD INCOMPATIBLE** Session configuration can no longer be disabled (no more
  ``session=False``)
- **BACKWARD INCOMPATIBLE** Engines can no longer be bound to ``MetaData`` objects
- **BACKWARD INCOMPATIBLE** Renamed the ``asphalt.sqlalchemy.util`` module to
  ``asphalt.sqlalchemy.utils``
- **BACKWARD INCOMPATIBLE** The ``connect_test_database()`` function in the ``util`` module was
  replaced with the ``clear_database()`` which has somewhat different semantics

**2.1.3** (2017-02-11)

- A better fix for the memory leak plugged in v2.1.2.

**2.1.2** (2017-02-11)

- Fixed a memory leak that was triggered by using the context's SQLAlchemy session

**2.1.1** (2016-12-19)

- Modified session finalization code to work around a suspected Python bug

**2.1.0** (2016-12-12)

- Added the ``commit_executor`` option that lets users specify which executor to use for running
  automatic commit() on context finish

**2.0.0** (2016-05-09)

- **BACKWARD INCOMPATIBLE** Migrated to Asphalt 2.0
- **BACKWARD INCOMPATIBLE** Removed all asynchronous API extensions (``asphalt.sqlalchemy.async``)
- **BACKWARD INCOMPATIBLE** Renamed ``asphalt.sqlalchemy.utils`` to ``asphalt.sqlalchemy.util`` to
  be consistent with the core library
- Allowed combining ``engines`` with default parameters

**1.0.0** (2016-01-06)

- Initial release
