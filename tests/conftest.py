import os

import pytest


@pytest.fixture
def mysql_url():
    try:
        return os.environ['MYSQL_URL']
    except KeyError:
        pytest.skip('MYSQL_URL environment variable is not set')


@pytest.fixture
def postgresql_url():
    try:
        return os.environ['POSTGRESQL_URL']
    except KeyError:
        pytest.skip('POSTGRESQL_URL environment variable is not set')
