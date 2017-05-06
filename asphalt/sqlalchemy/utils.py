import os
from typing import Iterable

from sqlalchemy.engine import Engine
from sqlalchemy.sql.schema import MetaData
from typeguard import check_argument_types


def clear_database(engine: Engine, schemas: Iterable[str] = ()) -> None:
    """
    Clear any tables from an existing database.

    For SQLite engines, the target database file will be deleted and a new one is created in its
    place.

    :param engine: the engine to use
    :param schemas: full list of schema names to expect (ignored for SQLite)

    """
    assert check_argument_types()
    if engine.dialect.name == 'sqlite':
        # SQLite does not support dropping constraints and it's faster to just delete the file
        if engine.url.database not in (None, ':memory:') and os.path.isfile(engine.url.database):
            os.remove(engine.url.database)
    else:
        metadatas = []
        for schema in (None,) + tuple(schemas):
            # Reflect the schema to get the list of the tables, views and constraints
            metadata = MetaData()
            metadata.reflect(engine, schema=schema, views=True)
            metadatas.append(metadata)

        for metadata in metadatas:
            metadata.drop_all(engine, checkfirst=False)
