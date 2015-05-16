from sqlalchemy.engine import create_engine
from asphalt.core.concurrency import set_event_loop
import pytest


@pytest.fixture(autouse=True)
def setup_asphalt_event_loop(event_loop):
    set_event_loop(event_loop)


@pytest.yield_fixture
def connection():
    engine = create_engine('sqlite:///', connect_args={'check_same_thread': False})
    connection = engine.connect()
    connection.execute('CREATE TABLE foo (id INTEGER PRIMARY KEY)')
    yield connection
    connection.close()
    engine.dispose()
