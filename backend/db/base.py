from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base. Every model imports from here so that a single
    metadata registry knows about all tables when create_all runs."""
