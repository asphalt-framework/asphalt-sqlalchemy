from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.sql.ddl import CreateSchema, DropSchema
from sqlalchemy.sql.schema import Column, ForeignKey, MetaData, Table
from sqlalchemy.sql.sqltypes import Integer

from asphalt.sqlalchemy import clear_async_database, clear_database

pytestmark = pytest.mark.anyio


@pytest.fixture
def connection(sync_engine: Engine) -> Generator[Connection, Any, None]:
    with sync_engine.connect() as conn:
        metadata = MetaData()
        Table("table", metadata, Column("column1", Integer, primary_key=True))
        Table("table2", metadata, Column("fk_column", ForeignKey("table.column1")))
        if conn.dialect.name != "sqlite":
            conn.execute(CreateSchema("altschema"))
            Table("table3", metadata, Column("fk_column", Integer), schema="altschema")

        metadata.create_all(conn)

        yield conn

        if conn.dialect.name != "sqlite":
            metadata.drop_all(conn)
            conn.execute(DropSchema("altschema"))


@pytest.fixture
async def async_connection(
    async_engine: AsyncEngine,
) -> AsyncGenerator[AsyncConnection]:
    async with async_engine.connect() as conn:
        metadata = MetaData()
        Table("table", metadata, Column("column1", Integer, primary_key=True))
        Table("table2", metadata, Column("fk_column", ForeignKey("table.column1")))
        if conn.dialect.name != "sqlite":
            await conn.execute(CreateSchema("altschema"))
            Table("table3", metadata, Column("fk_column", Integer), schema="altschema")

        await conn.run_sync(metadata.create_all)

        yield conn

        if conn.dialect.name != "sqlite":
            await conn.run_sync(metadata.drop_all)
            await conn.execute(DropSchema("altschema"))


def test_clear_database(connection: Connection) -> None:
    clear_database(
        connection, ["altschema"] if connection.dialect.name != "sqlite" else []
    )
    metadata = MetaData()
    metadata.reflect(connection)
    assert len(metadata.tables) == 0

    if connection.dialect.name != "sqlite":
        alt_metadata = MetaData(schema="altschema")
        alt_metadata.reflect(connection)
        assert len(alt_metadata.tables) == 0


async def test_clear_async_database(async_connection: AsyncConnection) -> None:
    await clear_async_database(
        async_connection,
        ["altschema"] if async_connection.dialect.name != "sqlite" else [],
    )
    metadata = MetaData()
    await async_connection.run_sync(metadata.reflect)
    assert len(metadata.tables) == 0

    if async_connection.dialect.name != "sqlite":
        alt_metadata = MetaData(schema="altschema")
        await async_connection.run_sync(alt_metadata.reflect)
        assert len(alt_metadata.tables) == 0
