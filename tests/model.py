from sqlalchemy.orm import declarative_base
from sqlalchemy.schema import Column
from sqlalchemy.types import Integer, Unicode

Base = declarative_base()


class Person(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True)
    name = Column(Unicode(100), nullable=False)
