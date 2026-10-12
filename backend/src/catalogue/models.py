"""Immutable catalogue tables and shared provider identities."""

from sqlalchemy import CheckConstraint, Text
from sqlmodel import Field, SQLModel


class Title(SQLModel, table=True):
    __tablename__ = "title"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 0 AND 10"),
        CheckConstraint("votes >= 0"),
        {"sqlite_with_rowid": False},
    )

    imdb_id: str = Field(primary_key=True, sa_type=Text)
    primary_title: str = Field(sa_type=Text)
    year: int | None = None
    kind: str = Field(sa_type=Text)
    rating: float | None = None
    votes: int | None = None


class Alias(SQLModel, table=True):
    __tablename__ = "alias"
    __table_args__ = {"sqlite_with_rowid": False}

    normalized: str = Field(primary_key=True, sa_type=Text)
    imdb_id: str = Field(primary_key=True, foreign_key="title.imdb_id", sa_type=Text)


class Metadata(SQLModel, table=True):
    __tablename__ = "metadata"

    key: str = Field(primary_key=True, sa_type=Text)
    value: str = Field(sa_type=Text)


class ProviderMapping(SQLModel, table=True):
    __tablename__ = "provider_mapping"

    provider: str = Field(primary_key=True, sa_type=Text)
    provider_id: str = Field(primary_key=True, sa_type=Text)
    imdb_id: str = Field(sa_type=Text)
