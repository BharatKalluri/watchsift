import httpx
import pytest
from pydantic import SecretStr, ValidationError

from src.catalogue.models import IMDbCache
from src.catalogue.ratings_providers import OMDbRatingsProvider, ReelDBRatingsProvider
from src.catalogue.schemas import RatingsProviderRequest, RatingsProviderResult
from src.catalogue.service import resolve
from src.database import operations_session


def payload(**changes):
    return {
        "Response": "True",
        "imdbID": "tt6",
        "Title": "Different upstream title",
        "Year": "2021",
        "Type": "movie",
        "imdbRating": "5.7",
        "imdbVotes": "4,477",
        **changes,
    }


@pytest.fixture
def reel(config, monkeypatch):
    config.reeldb_api_key = SecretStr("reel-test-key")
    original = httpx.Client.get
    calls = []
    data = payload()

    def get(self, url, *, params):
        if url == ReelDBRatingsProvider.endpoint:
            calls.append(params)
            return httpx.Response(200, json=data, request=httpx.Request("GET", url))
        return original(self, url, params=params)

    monkeypatch.setattr(httpx.Client, "get", get)
    return data, calls


async def lookup(client, title="Unrated", **hints):
    return await client.post(
        "/v1/resolve",
        json={"cards": [{"request_id": "0", "netflix_id": "123", "title": title, **hints}]},
    )


@pytest.mark.parametrize("missing", ["both", "rating", "votes"])
async def test_missing_metadata_falls_back_and_is_cached(client, config, omdb, reel, missing):
    omdb[0]["tt6"].update(
        imdbRating="6.0" if missing == "votes" else "N/A",
        imdbVotes="100" if missing == "rating" else "N/A",
    )
    first = await lookup(client)
    assert first.status_code == 200
    assert first.json()["results"][0]["rating"] == {
        "imdb_id": "tt6",
        "rating": 5.7,
        "votes": 4477,
    }
    assert reel[1] == [{"apikey": "reel-test-key", "i": "tt6"}]
    assert (await lookup(client)).json() == first.json()
    assert len(reel[1]) == len(omdb[1]) == 1
    with operations_session(config.database_url.get_secret_value()) as db:
        row = db.get(IMDbCache, "tt6")
        assert (row.title, row.year, row.rating, row.votes) == ("Unrated", 2022, 5.7, 4477)


async def test_existing_unrated_cache_gets_fallback(client, config, omdb, reel):
    config.reeldb_api_key = SecretStr("")
    assert (await lookup(client)).json()["results"][0]["rating"] is None
    config.reeldb_api_key = SecretStr("reel-test-key")
    assert (await lookup(client)).json()["results"][0]["rating"]["votes"] == 4477
    assert len(omdb[1]) == len(reel[1]) == 1


@pytest.mark.parametrize(
    "title,hints", [("Same Name", {}), ("Unknown", {}), ("Unrated", {"year": 2020})]
)
async def test_complete_missing_or_rejected_matches_skip_reeldb(client, reel, title, hints):
    assert (await lookup(client, title, **hints)).status_code == 200
    assert reel[1] == []


@pytest.mark.parametrize(
    "changes",
    [
        {"Response": "False", "Error": "Movie not found!"},
        {"imdbRating": "N/A"},
        {"imdbVotes": "N/A"},
    ],
)
async def test_reeldb_without_complete_ratings_leaves_title_unbadged(client, reel, changes):
    reel[0].update(changes)
    response = await lookup(client)
    assert response.status_code == 200
    assert response.json()["results"][0]["rating"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"imdbID": "tt999"},
        {"imdbRating": "11"},
        {"imdbVotes": "-1"},
        {"Response": "False", "Error": "Invalid API key!"},
    ],
)
async def test_invalid_fallback_is_private_and_preserves_omdb_metadata(
    client, config, reel, changes
):
    reel[0].update(changes)
    response = await lookup(client)
    assert response.status_code == 503
    assert response.json() == {"detail": "Ratings unavailable"}
    assert "reel-test-key" not in response.text
    with operations_session(config.database_url.get_secret_value()) as db:
        row = db.get(IMDbCache, "tt6")
        assert (row.title, row.year, row.rating, row.votes) == ("Unrated", 2022, None, None)


@pytest.mark.parametrize("status", [403, 429, 500])
async def test_fallback_http_errors_are_retryable(client, reel, monkeypatch, status):
    original = httpx.Client.get

    def get(self, url, *, params):
        if url == ReelDBRatingsProvider.endpoint:
            return httpx.Response(status, request=httpx.Request("GET", url))
        return original(self, url, params=params)

    monkeypatch.setattr(httpx.Client, "get", get)
    assert (await lookup(client)).status_code == 503


def test_evaluation_fallback_does_not_write_cache(config, reel):
    from src.catalogue.schemas import Card

    result = resolve(
        config, [Card(request_id="0", netflix_id="123", title="Unrated")], use_mappings=False
    )
    assert result.results[0].rating.votes == 4477
    with operations_session(config.database_url.get_secret_value()) as db:
        assert db.get(IMDbCache, "tt6") is None


@pytest.mark.parametrize("provider", [OMDbRatingsProvider, ReelDBRatingsProvider])
def test_ratings_provider_contract(provider, monkeypatch):
    def respond(request):
        assert request.url.params["i"] == "tt6"
        return httpx.Response(200, json=payload(), request=request)

    monkeypatch.setattr(
        httpx.Client,
        "get",
        lambda self, url, *, params: respond(httpx.Request("GET", url, params=params)),
    )
    with httpx.Client() as client:
        result = provider(client, SecretStr("test")).fetch(RatingsProviderRequest(imdb_id="tt6"))
    assert isinstance(result, RatingsProviderResult)
    assert result.votes == 4477
    with pytest.raises(ValidationError):
        RatingsProviderRequest()


async def test_shared_imdb_cache_prevents_duplicate_fallback(client, reel):
    response = await client.post(
        "/v1/resolve",
        json={
            "cards": [
                {"request_id": "0", "netflix_id": "123", "title": "Unrated"},
                {
                    "request_id": "1",
                    "provider": "primevideo",
                    "provider_id": "B000000001",
                    "title": "Unrated",
                },
            ]
        },
    )
    assert response.status_code == 200
    assert [r["rating"]["votes"] for r in response.json()["results"]] == [4477, 4477]
    assert len(reel[1]) == 1


async def test_fallback_timeout_is_retryable(client, reel, monkeypatch):
    original = httpx.Client.get

    def get(self, url, *, params):
        if url == ReelDBRatingsProvider.endpoint:
            raise httpx.ReadTimeout("upstream timeout")
        return original(self, url, params=params)

    monkeypatch.setattr(httpx.Client, "get", get)
    assert (await lookup(client)).status_code == 503
