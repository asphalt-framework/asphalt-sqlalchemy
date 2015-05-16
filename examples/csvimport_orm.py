"""
A simple example that imports a tab-delimited CSV file
(people.csv) into an SQLite database (people.db).

This version of the example uses the ORM instead of
core queries.
"""

import csv
import logging

from pathlib import Path
from sqlalchemy.ext.declarative.api import declarative_base

from asphalt.core.component import ContainerComponent
from asphalt.core.context import Context
from asphalt.core.runner import run_application
from asphalt.core.util import stop_event_loop, blocking
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import Integer, Unicode

Base = declarative_base()


class Person(Base):
    __tablename__ = 'people'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode, nullable=False)
    city = Column(Unicode, nullable=False)
    phone = Column(Unicode, nullable=False)
    email = Column(Unicode, nullable=False)


class CSVImporterComponent(ContainerComponent):
    @blocking
    def start(self, ctx: Context):
        csv_path = Path(__file__).parent / 'people.csv'
        db_path = csv_path.with_name('people.db')

        # Remove any existing db file
        if db_path.exists():
            db_path.unlink()

        self.add_component('sqlalchemy', url='sqlite:///{}'.format(db_path),
                           metadata=Base.metadata)
        super().start(ctx)

        # Create the table
        Base.metadata.create_all()

        num_rows = 0
        with csv_path.open() as csvfile:
            reader = csv.reader(csvfile, delimiter='|')
            for name, city, phone, email in reader:
                num_rows += 1
                ctx.dbsession.add(Person(name=name, city=city, phone=phone, email=email))

        print('Imported %d rows of data' % num_rows)
        stop_event_loop()

run_application(CSVImporterComponent(), logging=logging.DEBUG)
