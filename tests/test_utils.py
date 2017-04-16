from sqlalchemy import create_engine
from sqlalchemy.sql.ddl import DropSchema, CreateSchema
from sqlalchemy.sql.schema import MetaData, Table, Column, ForeignKey
from sqlalchemy.sql.sqltypes import Integer
import pytest

from asphalt.sqlalchemy.utils import clear_database


@pytest.fixture(params=['sqlite-file', 'sqlite-memory', 'mysql', 'postgresql'])
def engine(request, tmpdir_factory):
    engine = None
    if request.param == 'sqlite-file':
        tmpdir = tmpdir_factory.mktemp('asphalt-sqlalchemy')
        db_path = str(tmpdir.join('test.db'))
        engine = create_engine('sqlite:///' + db_path)
    elif request.param == 'sqlite-memory':
        engine = create_engine('sqlite:///:memory:')
    elif request.param == 'mysql':
        url = request.getfixturevalue('mysql_url')
        engine = create_engine(url)
    elif request.param == 'postgresql':
        url = request.getfixturevalue('postgresql_url')
        engine = create_engine(url)

    if engine.dialect.name != 'sqlite':
        engine.execute(CreateSchema('altschema'))

    if request.param != 'sqlite-memory':
        metadata = MetaData()
        Table('table', metadata, Column('column1', Integer, primary_key=True))
        Table('table2', metadata, Column('fk_column', ForeignKey('table.column1')))
        if engine.dialect.name != 'sqlite':
            Table('table3', metadata, Column('fk_column', Integer), schema='altschema')

        metadata.create_all(engine)

    yield engine

    if engine.dialect.name != 'sqlite':
        metadata.drop_all(engine)
        engine.execute(DropSchema('altschema'))


def test_clear_database(engine):
    clear_database(engine, ['altschema'])
    metadata = MetaData()
    metadata.reflect(engine)
    assert len(metadata.tables) == 0

    if engine.dialect.name != 'sqlite':
        alt_metadata = MetaData(schema='altschema')
        alt_metadata.reflect(engine)
        assert len(alt_metadata.tables) == 0
