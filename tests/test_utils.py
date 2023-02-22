from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.sql.ddl import CreateSchema, DropSchema
from sqlalchemy.sql.schema import Column, ForeignKey, MetaData, Table
from sqlalchemy.sql.sqltypes import Integer

from asphalt.sqlalchemy.utils import clear_database


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
