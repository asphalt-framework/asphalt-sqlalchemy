import os

import pytest
from sqlalchemy import create_engine


@pytest.fixture(scope='session')
def patch_psycopg2():
    from psycopg2cffi import compat
    compat.register()


@pytest.fixture(scope='module')
def mysql_engine():
    try:
        url = os.environ['MYSQL_URL']
    except KeyError:
        pytest.skip('MYSQL_URL environment variable is not set')
    else:
        engine = create_engine(url)
        yield engine
        engine.dispose()


@pytest.fixture(scope='module')
def postgresql_engine(patch_psycopg2):
    try:
        url = os.environ['POSTGRESQL_URL']
    except KeyError:
        pytest.skip('POSTGRESQL_URL environment variable is not set')
    else:
        engine = create_engine(url)
        yield engine
        engine.dispose()


@pytest.fixture(scope='module')
def sqlite_memory_engine():
    engine = create_engine('sqlite:///:memory:', connect_args=dict(check_same_thread=False))
    yield engine
    engine.dispose()


@pytest.fixture(scope='module')
def sqlite_file_engine(tmpdir_factory):
    tmpdir = tmpdir_factory.mktemp('asphalt-sqlalchemy')
    db_path = tmpdir.join('test.db')
    engine = create_engine('sqlite:///%s' % db_path, connect_args=dict(check_same_thread=False))
    yield engine
    engine.dispose()
    if db_path.exists():
        db_path.remove()
