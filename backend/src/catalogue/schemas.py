import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Card(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_id: str = Field(min_length=1, max_length=64)
    netflix_id: str | None = Field(default=None, pattern=r"^\d{1,20}$")
    provider: str = Field(default="netflix", pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    provider_id: str | None = Field(
        default=None, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$"
    )
    title: str = Field(min_length=1, max_length=300)
    year: int | None = Field(default=None, ge=1870, le=2100)
    type: Literal["movie", "series"] | None = None

    raw_year: str | None = Field(default=None, max_length=300)
    duration: str | None = Field(default=None, max_length=300)
    row_label: str | None = Field(default=None, max_length=300)
    explicit_type: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def interpret_metadata(self):
        if self.year is None and self.raw_year and re.fullmatch(r"[0-9]{4}", self.raw_year):
            year = int(self.raw_year)
            if 1870 <= year <= 2100:
                self.year = year
        if self.type is None:
            if re.search(r"\b(episodes?|seasons?|limited series)\b", self.duration or "", re.I):
                self.type = "series"
            elif re.search(r"\b[0-9]+\s*[hm]\b", self.duration or "", re.I):
                self.type = "movie"
            elif self.explicit_type in ("movie", "series", "Movie", "TV Show"):
                self.type = {"Movie": "movie", "TV Show": "series"}.get(
                    self.explicit_type, self.explicit_type
                )
            else:
                movie = bool(re.search(r"\b(movies|films)\b", self.row_label or "", re.I))
                series = bool(re.search(r"\b(tv|shows|series)\b", self.row_label or "", re.I))
                if movie != series:
                    self.type = "movie" if movie else "series"
        return self

    @model_validator(mode="after")
    def provider_identity(self):
        if self.netflix_id is not None:
            if self.provider != "netflix" or self.provider_id not in (None, self.netflix_id):
                raise ValueError("Conflicting provider identity")
            self.provider_id = self.netflix_id
        if self.provider_id is None:
            raise ValueError("A provider ID is required")
        if self.provider == "netflix":
            if (
                not self.provider_id.isascii()
                or not self.provider_id.isdigit()
                or len(self.provider_id) > 20
            ):
                raise ValueError("Invalid Netflix ID")
            self.netflix_id = self.provider_id
        elif self.provider == "primevideo" and not re.fullmatch(
            r"[A-Z0-9]{10,26}", self.provider_id
        ):
            raise ValueError("Invalid Prime Video ID")
        return self


class ResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cards: list[Card] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def share_type_hints(self):
        hints = {}
        for card in self.cards:
            if card.type:
                hints.setdefault((card.provider, card.provider_id), set()).add(card.type)
        for card in self.cards:
            known = hints.get((card.provider, card.provider_id), set())
            if card.type is None and len(known) == 1:
                card.type = next(iter(known))
        return self


class Rating(BaseModel):
    imdb_id: str = Field(pattern=r"^tt\d+$")
    rating: float = Field(ge=0, le=10)
    votes: int = Field(ge=0)


class Resolution(BaseModel):
    request_id: str
    status: Literal["matched", "ambiguous", "not_found"]
    rating: Rating | None = None


class ResolveResponse(BaseModel):
    results: list[Resolution]
    dataset_version: str
    dataset_date: str
    matcher_version: str


class RatingsProviderRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=300)
    imdb_id: str | None = Field(default=None, pattern=r"^tt\d+$")
    year: int | None = Field(default=None, ge=1870, le=2100)
    type: Literal["movie", "series"] | None = None

    @model_validator(mode="after")
    def require_identity(self):
        if not self.title and not self.imdb_id:
            raise ValueError("A title or IMDb ID is required")
        return self


class RatingsProviderResult(BaseModel):
    imdb_id: str = Field(pattern=r"^tt\d+$")
    title: str = Field(min_length=1)
    year: int | None = Field(default=None, ge=1870, le=2100)
    type: Literal["movie", "series"]
    rating: float | None = Field(default=None, ge=0, le=10)
    votes: int | None = Field(default=None, ge=0)
