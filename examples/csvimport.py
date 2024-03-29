"""
A simple example that imports a tab-delimited CSV file (people.csv) into an SQLite
database (people.db).

This version of the example uses SQLAlchemy core.
"""

import csv
import logging
from pathlib import Path

from asphalt.core import (
    CLIApplicationComponent,
    Context,
    inject,
    resource,
    run_application,
)
from sqlalchemy.orm import Session
from sqlalchemy.sql.schema import Column, MetaData, Table
from sqlalchemy.sql.sqltypes import Integer, Unicode

logger = logging.getLogger(__name__)
metadata = MetaData()
people = Table(
    "people",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", Unicode, nullable=False),
    Column("city", Unicode, nullable=False),
    Column("phone", Unicode, nullable=False),
    Column("email", Unicode, nullable=False),
)


class CSVImporterComponent(CLIApplicationComponent):
    def __init__(self) -> None:
        super().__init__()
        self.csv_path = Path(__file__).with_name("people.csv")

    async def start(self, ctx: Context) -> None:
        # Remove the db file if it exists
        db_path = self.csv_path.with_name("people.db")
        if db_path.exists():
            db_path.unlink()

        self.add_component(
            "sqlalchemy",
            url=f"sqlite:///{db_path}",
            ready_callback=lambda bind, factory: metadata.create_all(bind),
        )
        await super().start(ctx)

    @inject
    async def run(self, ctx: Context, *, dbsession: Session = resource()) -> None:
        async with ctx.threadpool():
            num_rows = 0
            with self.csv_path.open() as csvfile:
                reader = csv.reader(csvfile, delimiter="|")
                for name, city, phone, email in reader:
                    num_rows += 1
                    dbsession.execute(
                        people.insert().values(
                            name=name, city=city, phone=phone, email=email
                        )
                    )

        logger.info("Imported %d rows of data", num_rows)


run_application(CSVImporterComponent(), logging=logging.DEBUG)
