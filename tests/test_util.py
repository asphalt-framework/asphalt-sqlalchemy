from sqlalchemy.sql.schema import MetaData, Table, Column, ForeignKey
from sqlalchemy.sql.sqltypes import Integer, Unicode
import pytest

from asphalt.sqlalchemy.util import connect_test_database


@pytest.fixture(params=['sqlite', 'mysql', 'postgresql'])
def database_url(request, tmpdir_factory):
    if request.param == 'sqlite':
        tmpdir = tmpdir_factory.mktemp('asphalt-sqlalchemy')
        db_path = str(tmpdir.join('test.db'))
        return 'sqlite:///' + db_path
    elif request.param == 'mysql':
        pytest.importorskip('cymysql')
        return 'mysql+cymysql://travis@localhost/asphalttest'
    elif request.param == 'postgresql':
        pytest.importorskip('psycopg2')
        return 'postgresql:///asphalttest'


def test_connect_test_database(database_url):
    metadata1 = MetaData()
    Table('table', metadata1, Column('column1', Integer, primary_key=True))
    Table('table2', metadata1, Column('fk_column', ForeignKey('table.column1', name='fk_1')))
    with connect_test_database(database_url) as connection:
        metadata1.create_all(connection)

    metadata2 = MetaData()
    Table('table', metadata2, Column('column2', Unicode(20)))
    with connect_test_database(database_url) as connection:
        metadata2.create_all(connection)
        metadata3 = MetaData(bind=connection, reflect=True)

    assert len(metadata3.tables) == 1

    table = metadata3.tables['table']
    assert len(table.columns) == 1
    assert 'column2' in table.columns.keys()
