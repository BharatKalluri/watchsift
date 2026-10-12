from contextlib import contextmanager
from functools import lru_cache

import certifi
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine, text

from src.catalogue.models import IMDbCache, ProviderMapping

OPERATIONS_TABLES = [ProviderMapping.__table__, IMDbCache.__table__]


@lru_cache(maxsize=32)
def database_engine(database_url: str):
    if not database_url:
        raise ValueError("DATABASE_URL is required")
    url = make_url(database_url)
    if url.get_backend_name() == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
        if url.query.get("sslrootcert") == "system":
            url = url.update_query_dict({"sslrootcert": certifi.where()})
        return create_engine(
            url, poolclass=NullPool, connect_args={"connect_timeout": 10}, hide_parameters=True
        )
    if url.get_backend_name() != "sqlite":
        raise ValueError("Unsupported database protocol")
    # SQLite is only used by isolated tests, with the same models and transactions.
    return create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 5},
        poolclass=NullPool,
        hide_parameters=True,
        execution_options={"schema_translate_map": {"watchsift": None}},
    )


@contextmanager
def operations_session(database_url: str):
    with Session(database_engine(database_url), expire_on_commit=False) as session:
        with session.begin():
            yield session


def init_operations(database_url: str) -> None:
    engine = database_engine(database_url)
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS watchsift"))
        SQLModel.metadata.create_all(connection, tables=OPERATIONS_TABLES)
