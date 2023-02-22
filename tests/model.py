from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Unicode


class Base(DeclarativeBase):
    pass


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100))
