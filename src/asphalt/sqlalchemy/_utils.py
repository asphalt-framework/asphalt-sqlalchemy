from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.future import Connection, Engine
from sqlalchemy.pool import ConnectionPoolEntry
from sqlalchemy.sql.schema import MetaData


def clear_database(engine: Engine | Connection, schemas: Iterable[str] = ()) -> None:
    """
    Clear any tables from an existing database using a synchronous connection/engine.

    :param engine: the engine or connection to use
    :param schemas: full list of schema names to expect (ignored for SQLite)

    """
    metadatas = []
    all_schemas: tuple[str | None, ...] = (None,)
    all_schemas += tuple(schemas)
    for schema in all_schemas:
        # Reflect the schema to get the list of the tables, views and constraints
        metadata = MetaData()
        metadata.reflect(engine, schema=schema, views=True)
        metadatas.append(metadata)

    for metadata in metadatas:
        metadata.drop_all(engine, checkfirst=False)


async def clear_async_database(
    connection: AsyncConnection, schemas: Iterable[str] = ()
) -> None:
    """
    Clear any tables from an existing database using an asynchronous connection.

    :param connection: the connection to use
    :param schemas: full list of schema names to expect (ignored for SQLite)

    """
    metadatas = []
    all_schemas: tuple[str | None, ...] = (None,)
    all_schemas += tuple(schemas)
    for schema in all_schemas:
        # Reflect the schema to get the list of the tables, views and constraints
        metadata = MetaData()
        await connection.run_sync(metadata.reflect, schema=schema, views=True)
        metadatas.append(metadata)

    for metadata in metadatas:
        await connection.run_sync(metadata.drop_all, checkfirst=False)


def apply_sqlite_hacks(engine: Engine | AsyncEngine) -> None:
    """
    Apply hacks for ``SAVEPOINT`` support on pysqlite based engines.

    This function is automatically called by the component, and only needs to be
    explicitly used by the developer when using an SQLite connection for database
    integration tests (the connection is passed to the component as the ``bind``
    option).

    .. seealso:: https://docs.sqlalchemy.org/en/14/dialects/sqlite.html\
#pysqlite-serializable

    :param engine: an engine using the sqlite dialect

    """

    def do_connect(
        dbapi_connection: sqlite3.Connection, connection_record: ConnectionPoolEntry
    ) -> None:
        # disable pysqlite's emitting of the BEGIN statement entirely.
        # also stops it from emitting COMMIT before any DDL.
        dbapi_connection.isolation_level = None

    def do_begin(conn: Connection) -> None:
        # emit our own BEGIN
        conn.exec_driver_sql("BEGIN")

    if not engine.dialect.name == "sqlite":
        raise ValueError(
            f"SQLite hacks can only applied to an engine with dialect "
            f"'sqlite', not {engine.dialect.name!r}"
        )

    sync_engine = engine.sync_engine if isinstance(engine, AsyncEngine) else engine
    event.listen(sync_engine, "connect", do_connect)
    event.listen(sync_engine, "begin", do_begin)
