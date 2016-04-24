"""
A simple example that imports a tab-delimited CSV file (people.csv) into an SQLite database
(people.db).
"""

import asyncio
import csv
import logging
from pathlib import Path

from asphalt.core import ContainerComponent, Context, run_application
from asyncio_extras.threads import threadpool
from sqlalchemy.sql.schema import MetaData, Table, Column
from sqlalchemy.sql.sqltypes import Integer, Unicode

logger = logging.getLogger(__name__)
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
    async def start(self, ctx: Context):
        csv_path = Path(__file__).parent / 'people.csv'
        db_path = csv_path.with_name('people.db')

        # Remove any existing db file
        if db_path.exists():
            db_path.unlink()

        self.add_component('sqlalchemy', url='sqlite:///{}'.format(db_path), metadata=metadata)
        await super().start(ctx)

        # Create the table
        metadata.create_all()

        num_rows = 0
        async with threadpool():
            with csv_path.open() as csvfile, ctx.sql.begin() as connection:
                reader = csv.reader(csvfile, delimiter='|')
                for name, city, phone, email in reader:
                    num_rows += 1
                    connection.execute(
                        people.insert().values(name=name, city=city, phone=phone, email=email))

        logger.info('Imported %d rows of data', num_rows)
        asyncio.get_event_loop().stop()

run_application(CSVImporterComponent(), logging=logging.DEBUG)
