"""
A simple example that imports a tab-delimited CSV file
(people.csv) into an SQLite database (people.db).
"""

from pathlib import Path
import csv
import logging

from asphalt.core.component import ContainerComponent
from asphalt.core.context import Context
from asphalt.core.runner import run_application
from asphalt.core.util import stop_event_loop, blocking
from sqlalchemy.sql.schema import MetaData, Table, Column
from sqlalchemy.sql.sqltypes import Integer, Unicode

metadata = MetaData()
people = Table(
    'people', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', Unicode, nullable=False),
    Column('city', Unicode, nullable=False),
    Column('phone', Unicode, nullable=False),
    Column('email', Unicode, nullable=False)
)


class CSVImporterComponent(ContainerComponent):
    @blocking
    def start(self, ctx: Context):
        csv_path = Path(__file__).parent / 'people.csv'
        db_path = csv_path.with_name('people.db')

        # Remove any existing db file
        if db_path.exists():
            db_path.unlink()

        self.add_component('sqlalchemy', url='sqlite:///{}'.format(db_path), metadata=metadata)
        super().start(ctx)

        # Create the table
        metadata.create_all()

        num_rows = 0
        with csv_path.open() as csvfile, ctx.sql.begin() as connection:
            reader = csv.reader(csvfile, delimiter='|')
            for name, city, phone, email in reader:
                num_rows += 1
                connection.execute(
                    people.insert().values(name=name, city=city, phone=phone, email=email))

        print('Imported %d rows of data' % num_rows)
        stop_event_loop()

run_application(CSVImporterComponent(), logging=logging.DEBUG)
