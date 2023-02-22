"""
A simple example that imports a tab-delimited CSV file (people.csv) into an SQLite
database (people.db).

This version of the example uses SQLAlchemy ORM.
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
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    city: Mapped[str]
    phone: Mapped[str]
    email: Mapped[str]


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
            ready_callback=lambda bind, factory: DeclarativeBase.metadata.create_all(
                bind
            ),
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
                    dbsession.add(
                        Person(name=name, city=city, phone=phone, email=email)
                    )

            # Emit pending INSERTs (though this would happen when the context ends
            # anyway)
            dbsession.flush()

        logger.info("Imported %d rows of data", num_rows)


run_application(CSVImporterComponent(), logging=logging.DEBUG)
