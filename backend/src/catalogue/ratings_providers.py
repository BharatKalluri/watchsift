import logging

import httpx
from pydantic import SecretStr

from src.catalogue import schemas

logger = logging.getLogger("uvicorn.error")


class RatingsProviderError(ValueError):
    """A provider failure with a message safe to log."""


class RatingsProvider:
    name: str
    endpoint: str

    def __init__(self, client: httpx.Client, api_key: SecretStr):
        self.client = client
        self.api_key = api_key

    @property
    def configured(self) -> bool:
        return bool(self.api_key.get_secret_value())

    def fetch(
        self, request: schemas.RatingsProviderRequest
    ) -> schemas.RatingsProviderResult | None:
        try:
            return self._fetch(request)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            reason = type(exc).__name__
            if isinstance(exc, httpx.HTTPStatusError):
                reason = f"HTTP {exc.response.status_code}"
            elif isinstance(exc, RatingsProviderError):
                reason = str(exc)
            logger.error("%s failed: imdb_id=%r reason=%s", self.name, request.imdb_id, reason)
            raise

    def _fetch(
        self, request: schemas.RatingsProviderRequest
    ) -> schemas.RatingsProviderResult | None:
        title, year, kind, imdb_id = request.title, request.year, request.type, request.imdb_id
        key = self.api_key.get_secret_value()
        if not key:
            raise RatingsProviderError("API key missing")
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
        # ReelDB uses HTTP 400 for its normal not-found response.
        if response.status_code != 400:
            response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            response.raise_for_status()
            raise RatingsProviderError("Invalid response: expected an object")
        if data.get("Response") == "False":
            if data.get("Error") in {
                "Movie not found!",
                "Series not found!",
                "Episode not found!",
            }:
                return None
            response.raise_for_status()
            reason = {
                "Invalid API key!": "Invalid API key",
                "Request limit reached!": "Request limit reached",
            }.get(data.get("Error"), "Upstream rejected request")
            raise RatingsProviderError(reason)
        response.raise_for_status()
        if data.get("Response") != "True" or not all(
            isinstance(data.get(field), str)
            for field in ("Title", "Year", "Type", "imdbID", "imdbRating", "imdbVotes")
        ):
            raise RatingsProviderError("Invalid response: missing or non-string fields")
        if imdb_id and data["imdbID"] != imdb_id:
            raise RatingsProviderError("Unexpected IMDb identity")
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
