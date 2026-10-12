import logging

import httpx
from pydantic import SecretStr

from src.catalogue import schemas

logger = logging.getLogger("uvicorn.error")


class RatingsProvider:
    name: str
    endpoint: str

    def __init__(self, client: httpx.Client, api_key: SecretStr):
        self.client = client
        self.api_key = api_key

    def fetch(
        self, request: schemas.RatingsProviderRequest
    ) -> schemas.RatingsProviderResult | None:
        title, year, kind, imdb_id = request.title, request.year, request.type, request.imdb_id
        key = self.api_key.get_secret_value()
        if not key:
            raise ValueError(f"{self.name} API key missing")
        params = {"apikey": key, "i" if imdb_id else "t": imdb_id or title}
        if year is not None:
            params["y"] = str(year)
        if kind is not None:
            params["type"] = kind
        logger.info(
            f"{self.name} request: title=%r imdb_id=%r year=%r type=%r",
            title,
            imdb_id,
            year,
            kind,
        )
        response = self.client.get(self.endpoint, params=params)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError(f"Invalid {self.name} response")
        if data.get("Response") == "False":
            if data.get("Error") in {
                "Movie not found!",
                "Series not found!",
                "Episode not found!",
            }:
                return None
            raise ValueError(f"{self.name} unavailable")
        if data.get("Response") != "True" or not all(
            isinstance(data.get(field), str)
            for field in ("Title", "Year", "Type", "imdbID", "imdbRating", "imdbVotes")
        ):
            raise ValueError(f"Invalid {self.name} fields")
        if imdb_id and data["imdbID"] != imdb_id:
            raise ValueError("Unexpected IMDb identity")
        if data["Type"] not in {"movie", "series"}:
            return None
        return schemas.RatingsProviderResult.model_validate(
            {
                "imdb_id": data["imdbID"],
                "title": data["Title"],
                "year": int(data["Year"][:4]) if data["Year"] != "N/A" else None,
                "type": data["Type"],
                "rating": data["imdbRating"] if data["imdbRating"] != "N/A" else None,
                "votes": int(data["imdbVotes"].replace(",", ""))
                if data["imdbVotes"] != "N/A"
                else None,
            }
        )


class OMDbRatingsProvider(RatingsProvider):
    name = "OMDb"
    endpoint = "https://www.omdbapi.com/"


class ReelDBRatingsProvider(RatingsProvider):
    name = "ReelDB"
    endpoint = "https://api.reeldb.io/omdb"
