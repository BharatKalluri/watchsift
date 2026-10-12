"""Shared provider identities and cached IMDb data."""

from typing import Annotated, Literal

from pydantic import StringConstraints
from sqlalchemy import BigInteger, CheckConstraint, Text
from sqlmodel import Field, SQLModel


class ProviderMapping(SQLModel, table=True):
    __tablename__ = "provider_mapping"
    __table_args__ = {"schema": "watchsift"}

    provider: str = Field(primary_key=True, sa_type=Text)
    provider_id: str = Field(primary_key=True, sa_type=Text)
    imdb_id: str = Field(sa_type=Text)
    lookup_title: str | None = Field(default=None, sa_type=Text)
    lookup_year: int | None = None
    lookup_type: str | None = Field(default=None, sa_type=Text)


class IMDbCache(SQLModel, table=True):
    __tablename__ = "imdb_cache"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 0 AND 10"),
        CheckConstraint("votes >= 0"),
        CheckConstraint("type IN ('movie', 'series')"),
        {"schema": "watchsift"},
    )

    imdb_id: Annotated[str, StringConstraints(pattern=r"^tt\d+$")] = Field(
        primary_key=True, sa_type=Text
    )
    title: str = Field(sa_type=Text, min_length=1)
    year: int | None = None
    type: Literal["movie", "series"] = Field(sa_type=Text)
    rating: float | None = Field(default=None, ge=0, le=10)
    votes: int | None = Field(default=None, ge=0, sa_type=BigInteger)
    fetched_at: int = Field(ge=0, sa_type=BigInteger)
