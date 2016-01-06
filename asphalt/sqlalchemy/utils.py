import os

from sqlalchemy.engine import create_engine, Connection
from sqlalchemy.sql.ddl import DropConstraint
from sqlalchemy.sql.schema import MetaData
from typeguard import check_argument_types


def connect_test_database(url: str, **engine_kwargs) -> Connection:
    """
    Connect to the given database and drops any existing tables in it.

    For SQLite URLs pointing to a file, the target database file will be deleted and a new one is
    created in its place.

    .. seealso:: :func:`sqlalchemy.create_engine`

    :param url: connection URL for the database
    :param engine_kwargs: additional keyword arguments passed to :func:`sqlalchemy.create_engine`
    :return: a connection object

    """
    check_argument_types()
    engine = create_engine(url, **engine_kwargs)

    if engine.dialect.name == 'sqlite':
        # SQLite does not support dropping constraints and it's faster to just delete the file
        if engine.url.database not in (None, ':memory:') and os.path.isfile(engine.url.database):
            os.remove(engine.url.database)

        connection = engine.connect()
    else:
        # Reflect the schema to get the list of the tables and constraints left over from the
        # previous run
        connection = engine.connect()
        metadata = MetaData(connection, reflect=True)

        # Drop all the foreign key constraints so we can drop the tables in any order
        for table in metadata.tables.values():
            for fk in table.foreign_keys:
                connection.execute(DropConstraint(fk.constraint))

        # Drop the tables
        metadata.drop_all()

    return connection
