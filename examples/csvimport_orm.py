"""
A simple example that imports a tab-delimited CSV file (people.csv) into an SQLite database
(people.db).

This version of the example uses SQLAlchemy ORM.
"""

import csv
import logging
from pathlib import Path

from asphalt.core import CLIApplicationComponent, Context, run_application
from sqlalchemy.ext.declarative.api import declarative_base
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import Integer, Unicode

logger = logging.getLogger(__name__)
Base = declarative_base()


class Person(Base):
    __tablename__ = 'people'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode, nullable=False)
    city = Column(Unicode, nullable=False)
    phone = Column(Unicode, nullable=False)
    email = Column(Unicode, nullable=False)


class CSVImporterComponent(CLIApplicationComponent):
    def __init__(self):
        super().__init__()
        self.csv_path = Path(__file__).with_name('people.csv')

    async def start(self, ctx: Context):
        # Remove the db file if it exists
        db_path = self.csv_path.with_name('people.db')
        if db_path.exists():
            db_path.unlink()

        self.add_component('sqlalchemy', url='sqlite:///{}'.format(db_path),
                           ready_callback=lambda bind, factory: Base.metadata.create_all(bind))
        await super().start(ctx)

    async def run(self, ctx: Context):
        async with ctx.threadpool():
            num_rows = 0
            with self.csv_path.open() as csvfile:
                reader = csv.reader(csvfile, delimiter='|')
                for name, city, phone, email in reader:
                    num_rows += 1
                    ctx.sql.add(Person(name=name, city=city, phone=phone, email=email))

            # Emit pending INSERTs (though this would happen when the context ends anyway)
            ctx.sql.flush()

        logger.info('Imported %d rows of data', num_rows)

run_application(CSVImporterComponent(), logging=logging.DEBUG)
