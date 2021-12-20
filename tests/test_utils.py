import pytest
from sqlalchemy.sql.ddl import CreateSchema, DropSchema
from sqlalchemy.sql.schema import Column, ForeignKey, MetaData, Table
from sqlalchemy.sql.sqltypes import Integer

from asphalt.sqlalchemy.utils import clear_database


@pytest.fixture(params=['sqlite_file', 'sqlite_memory', 'mysql', 'postgresql'])
def engine(request):
    engine = request.getfixturevalue('%s_engine' % request.param)
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
    clear_database(engine, ['altschema'] if engine.dialect.name != 'sqlite' else [])
    metadata = MetaData()
    metadata.reflect(engine)
    assert len(metadata.tables) == 0

    if engine.dialect.name != 'sqlite':
        alt_metadata = MetaData(schema='altschema')
        alt_metadata.reflect(engine)
        assert len(alt_metadata.tables) == 0
