Version history
===============

This library adheres to `Semantic Versioning <http://semver.org/>`_.

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
