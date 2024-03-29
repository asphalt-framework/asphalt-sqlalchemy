from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Generator
from typing import Any, cast

import pytest
from _pytest.fixtures import SubRequest
from pytest import TempPathFactory
from pytest_lazy_fixtures import lf
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.future import Engine, create_engine

from asphalt.sqlalchemy.utils import apply_sqlite_hacks


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def psycopg_url() -> str:  # type: ignore[return]
    pytest.importorskip("asyncmy", reason="asyncmy is not available")
    try:
        return os.environ["POSTGRESQL_URL"]
    except KeyError:
        pytest.skip("POSTGRESQL_URL environment variable is not set")


@pytest.fixture(scope="session")
def mysql_url() -> str:  # type: ignore[return]
    try:
        return os.environ["MYSQL_URL"]
    except KeyError:
        pytest.skip("MYSQL_URL environment variable is not set")


@pytest.fixture(scope="session")
def asyncmy_url(mysql_url: str) -> str:
    pytest.importorskip("asyncmy", reason="asyncmy is not available")
    return mysql_url.replace("pymysql", "asyncmy")


@pytest.fixture(scope="session")
def pymysql_engine(mysql_url: str) -> Generator[Engine, Any, None]:
    engine = create_engine(mysql_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def psycopg_engine(psycopg_url: str) -> Generator[Engine, Any, None]:
    engine = create_engine(psycopg_url, echo=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def sqlite_memory_engine() -> Generator[Engine, Any, None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args=dict(check_same_thread=False)
    )
    apply_sqlite_hacks(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def sqlite_file_engine(
    tmp_path_factory: TempPathFactory,
) -> Generator[Engine, Any, None]:
    db_path = tmp_path_factory.mktemp("asphalt-sqlalchemy") / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args=dict(check_same_thread=False)
    )
    apply_sqlite_hacks(engine)
    yield engine
    engine.dispose()
    if db_path.exists():
        db_path.unlink()


@pytest.fixture(scope="session")
async def aiosqlite_memory_engine() -> AsyncGenerator[AsyncEngine, Any]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    apply_sqlite_hacks(engine)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def aiosqlite_file_engine(
    tmp_path_factory: TempPathFactory,
) -> AsyncGenerator[AsyncEngine, Any]:
    db_path = tmp_path_factory.mktemp("asphalt-sqlalchemy") / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    apply_sqlite_hacks(engine)
    yield engine
    await engine.dispose()
    if db_path.exists():
        db_path.unlink()


@pytest.fixture(scope="session")
async def psycopg_async_engine(psycopg_url: str) -> AsyncGenerator[AsyncEngine, Any]:
    engine = create_async_engine(psycopg_url)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def asyncmy_engine(asyncmy_url: str) -> AsyncGenerator[AsyncEngine, Any]:
    engine = create_async_engine(asyncmy_url)
    yield engine
    await engine.dispose()


@pytest.fixture(
    params=[
        lf("sqlite_memory_engine"),
        lf("sqlite_file_engine"),
        lf("pymysql_engine"),
        lf("psycopg_engine"),
    ],
    scope="session",
)
def sync_engine(request: SubRequest) -> Engine:
    return cast(Engine, request.param)


@pytest.fixture(
    params=[
        lf("aiosqlite_memory_engine"),
        lf("aiosqlite_file_engine"),
        lf("psycopg_async_engine"),
        lf("asyncmy_engine"),
    ],
    scope="session",
)
async def async_engine(request: SubRequest) -> AsyncEngine:
    return cast(AsyncEngine, request.param)
