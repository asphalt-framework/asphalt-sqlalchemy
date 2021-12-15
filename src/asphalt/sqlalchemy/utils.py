from typing import Iterable, Optional, Tuple  # noqa: F401

from sqlalchemy.engine import Connectable
from sqlalchemy.sql.schema import MetaData
from typeguard import check_argument_types


def clear_database(engine: Connectable, schemas: Iterable[str] = ()) -> None:
    """
    Clear any tables from an existing database.

    :param engine: the engine or connection to use
    :param schemas: full list of schema names to expect (ignored for SQLite)

    """
    assert check_argument_types()
    metadatas = []
    all_schemas = (None,)  # type: Tuple[Optional[str], ...]
    all_schemas += tuple(schemas)
    for schema in all_schemas:
        # Reflect the schema to get the list of the tables, views and constraints
        metadata = MetaData()
        metadata.reflect(engine, schema=schema, views=True)
        metadatas.append(metadata)

    for metadata in metadatas:
        metadata.drop_all(engine, checkfirst=False)
