from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine, text

from src.catalogue.models import Alias, Metadata, ProviderMapping, Title

CATALOGUE_TABLES = [model.__table__ for model in (Title, Alias, Metadata)]
OPERATIONS_TABLES = [ProviderMapping.__table__]


@lru_cache(maxsize=32)
def database_engine(path: Path, *, readonly: bool = False):
    url = (
        f"sqlite:///{path.as_uri()}?mode=ro&immutable=1&uri=true"
        if readonly
        else f"sqlite:///{path}"
    )
    # No pooled connections can hold an old snapshot or a replaced file open.
    return create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 5},
        poolclass=NullPool,
        hide_parameters=True,
    )


@contextmanager
def catalogue_connection(data_dir: Path):
    # Resolve once: in-flight requests finish on the snapshot they opened.
    path = (data_dir / "current.sqlite3").resolve(strict=True)
    with Session(database_engine(path, readonly=True)) as session:
        yield session


@contextmanager
def operations_session(data_dir: Path):
    with Session(database_engine((data_dir / "operations.sqlite3").resolve())) as session:
        with session.begin():
            yield session


def init_operations(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    engine = database_engine((data_dir / "operations.sqlite3").resolve())
    with engine.connect() as connection:
        connection.execute(text("PRAGMA journal_mode=WAL"))
    with engine.begin() as connection:
        connection.execute(text("BEGIN IMMEDIATE"))
        # Remove retired reporting data without touching shared title mappings.
        for table in ("metric", "metric_receipt", "unmatched", "unmatched_legacy"):
            connection.execute(text(f"DROP TABLE IF EXISTS {table}"))
        SQLModel.metadata.create_all(connection, tables=OPERATIONS_TABLES)
