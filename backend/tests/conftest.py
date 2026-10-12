from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url

from src.config import Settings
from src.database import init_operations
from src.main import create_app


@pytest.fixture
def config(tmp_path):
    config = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'operations.sqlite3'}",
        requests_per_minute=1000,
        OMDB_API_KEY="test-key",
        REELDB_API_KEY="",
    )
    init_operations(config.database_url.get_secret_value())
    return config


@pytest.fixture
def database_path(config):
    return Path(make_url(config.database_url.get_secret_value()).database)


@pytest.fixture(autouse=True)
def omdb(monkeypatch):
    titles = {
        "tt1": {
            "Title": "Same Name",
            "Year": "2020",
            "Type": "movie",
            "imdbRating": "7.0",
            "imdbVotes": "1,000",
        },
        "tt2": {
            "Title": "Same Name",
            "Year": "2021",
            "Type": "movie",
            "imdbRating": "8.0",
            "imdbVotes": "999",
        },
        "tt3": {
            "Title": "Same Name",
            "Year": "2020–",
            "Type": "series",
            "imdbRating": "8.5",
            "imdbVotes": "5,000",
        },
        "tt5": {
            "Title": "Kumbalangi Nights",
            "Year": "2019",
            "Type": "movie",
            "imdbRating": "8.0",
            "imdbVotes": "100",
        },
        "tt6": {
            "Title": "Unrated",
            "Year": "2022",
            "Type": "movie",
            "imdbRating": "N/A",
            "imdbVotes": "N/A",
        },
    }
    calls = []

    def get(self, url, *, params):
        calls.append(params)
        found = None
        if params.get("i"):
            found = params["i"] if params["i"] in titles else None
        elif params["t"] == "Alternate Title":
            found = "tt1"
        else:
            for imdb_id, title in titles.items():
                if (
                    title["Title"] == params["t"]
                    and (not params.get("y") or title["Year"][:4] == params["y"])
                    and (not params.get("type") or title["Type"] == params["type"])
                ):
                    found = imdb_id
                    break
        data = (
            {"Response": "True", "imdbID": found, **titles[found]}
            if found
            else {"Response": "False", "Error": "Movie not found!"}
        )
        return httpx.Response(200, json=data, request=httpx.Request("GET", "https://omdb.test/"))

    monkeypatch.setattr(httpx.Client, "get", get)
    return titles, calls


@pytest.fixture
async def client(config):
    app = create_app(config)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
