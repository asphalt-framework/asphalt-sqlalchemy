import os
from asyncio import new_event_loop, set_event_loop

import pytest
import pytest_asyncio
from pytest_lazyfixture import lazy_fixture
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.future import Engine, create_engine

from asphalt.sqlalchemy.utils import apply_sqlite_hacks


@pytest.fixture(scope="session")
def event_loop():
    # Required for session scoped async fixtures
    loop = new_event_loop()
    set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def psycopg2_url() -> str:  # type: ignore[return]
    try:
        return os.environ["POSTGRESQL_URL"]
    except KeyError:
        pytest.skip("POSTGRESQL_URL environment variable is not set")


@pytest.fixture(scope="session")
def asyncpg_url(psycopg2_url) -> str:
    pytest.importorskip("asyncpg", reason="asyncpg is not available")
    return psycopg2_url.replace("psycopg2", "asyncpg")


@pytest.fixture(scope="session")
def mysql_url() -> str:  # type: ignore[return]
    try:
        return os.environ["MYSQL_URL"]
    except KeyError:
        pytest.skip("MYSQL_URL environment variable is not set")


@pytest.fixture(scope="session")
def asyncmy_url(mysql_url) -> str:
    pytest.importorskip("asyncmy", reason="asyncmy is not available")
    return mysql_url.replace("pymysql", "asyncmy")


@pytest.fixture(scope="session")
def patch_psycopg2():
    from psycopg2cffi import compat

    compat.register()


@pytest.fixture(scope="session")
def pymysql_engine(mysql_url):
    engine = create_engine(mysql_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def psycopg2_engine(patch_psycopg2, psycopg2_url):
    engine = create_engine(psycopg2_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def sqlite_memory_engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args=dict(check_same_thread=False)
    )
    apply_sqlite_hacks(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def sqlite_file_engine(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("asphalt-sqlalchemy") / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args=dict(check_same_thread=False)
    )
    apply_sqlite_hacks(engine)
    yield engine
    engine.dispose()
    if db_path.exists():
        db_path.unlink()


@pytest_asyncio.fixture(scope="session")
async def aiosqlite_memory_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    apply_sqlite_hacks(engine)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def aiosqlite_file_engine(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("asphalt-sqlalchemy") / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    apply_sqlite_hacks(engine)
    yield engine
    await engine.dispose()
    if db_path.exists():
        db_path.unlink()


@pytest_asyncio.fixture(scope="session")
async def asyncpg_engine(asyncpg_url):
    engine = create_async_engine(asyncpg_url)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def asyncmy_engine(asyncmy_url):
    engine = create_async_engine(asyncmy_url)
    yield engine
    await engine.dispose()


@pytest.fixture(
    params=[
        lazy_fixture("sqlite_memory_engine"),
        lazy_fixture("sqlite_file_engine"),
        lazy_fixture("pymysql_engine"),
        lazy_fixture("psycopg2_engine"),
    ],
    scope="session",
)
def sync_engine(request) -> Engine:
    return request.param


@pytest_asyncio.fixture(
    params=[
        lazy_fixture("aiosqlite_memory_engine"),
        lazy_fixture("aiosqlite_file_engine"),
        lazy_fixture("asyncpg_engine"),
        lazy_fixture("asyncmy_engine"),
    ],
    scope="session",
)
async def async_engine(request) -> AsyncEngine:
    return request.param
