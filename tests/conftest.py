from sqlalchemy.engine import create_engine
import pytest

pytest_plugins = ['asphalt.core.pytest_plugin']


@pytest.yield_fixture
def connection():
    engine = create_engine('sqlite:///', connect_args={'check_same_thread': False})
    connection = engine.connect()
    connection.execute('CREATE TABLE foo (id INTEGER PRIMARY KEY)')
    yield connection
    connection.close()
    engine.dispose()
