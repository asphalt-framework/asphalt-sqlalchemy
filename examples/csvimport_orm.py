"""
A simple example that imports a tab-delimited CSV file (people.csv) into an SQLite database
(people.db).

This version of the example uses the ORM instead of core queries.
"""

import asyncio
import csv
import logging
from pathlib import Path

from asphalt.core import ContainerComponent, Context, run_application
from asyncio_extras.threads import threadpool
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


class ApplicationrComponent(ContainerComponent):
    async def start(self, ctx: Context):
        csv_path = Path(__file__).parent / 'people.csv'
        db_path = csv_path.with_name('people.db')

        # Remove any existing db file
        if db_path.exists():
            db_path.unlink()

        self.add_component('sqlalchemy', url='sqlite:///{}'.format(db_path),
                           metadata=Base.metadata)
        await super().start(ctx)

        # Create the table
        Base.metadata.create_all()

        async with threadpool():
            num_rows = 0
            with csv_path.open() as csvfile:
                reader = csv.reader(csvfile, delimiter='|')

                # Import each row into the session as a new Person instance
                for name, city, phone, email in reader:
                    num_rows += 1
                    ctx.dbsession.add(Person(name=name, city=city, phone=phone, email=email))

        logger.info('Imported %d rows of data', num_rows)
        asyncio.get_event_loop().stop()

run_application(ApplicationrComponent(), logging=logging.DEBUG)
