"""Run the real API with synthetic OMDb responses for packaged extension tests."""

from functools import partial
from unittest.mock import patch

import httpx

from src.main import app

TITLES = {
    "tt0111161": ("The Shawshank Redemption", "1994", "7.0", "1,000"),
    "tt0052077": ("Plan 9 from Outer Space", "1958", "6.9", "10,000"),
}


def respond(request):
    for imdb_id, (title, year, rating, votes) in TITLES.items():
        if request.url.params.get("i") == imdb_id or request.url.params.get("t") == title:
            return httpx.Response(
                200,
                json={
                    "Response": "True",
                    "imdbID": imdb_id,
                    "Title": title,
                    "Year": year,
                    "Type": "movie",
                    "imdbRating": rating,
                    "imdbVotes": votes,
                },
            )
    return httpx.Response(200, json={"Response": "False", "Error": "Movie not found!"})


patch(
    "src.catalogue.service.httpx.Client",
    partial(httpx.Client, transport=httpx.MockTransport(respond)),
).start()

__all__ = ["app"]
