import httpx
import pytest
from pydantic import SecretStr, ValidationError

from src.catalogue import service
from src.catalogue.models import IMDbCache, ProviderMapping
from src.catalogue.ratings_providers import OMDbRatingsProvider, ReelDBRatingsProvider
from src.catalogue.schemas import RatingsProviderRequest, RatingsProviderResult
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


def test_fallback_ratings_copy_without_mutating_omdb_row():
    original = IMDbCache(imdb_id="tt6", title="Unrated", year=2022, type="movie", fetched_at=1)
    source = IMDbCache(
        imdb_id="tt6", title="Other", type="movie", rating=5.7, votes=4477, fetched_at=2
    )
    before = original.model_dump()
    rated = service._with_ratings(original, source)
    assert original.model_dump() == before
    assert (rated.title, rated.year, rated.rating, rated.votes) == ("Unrated", 2022, 5.7, 4477)
    assert rated.fetched_at == 1


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


async def test_unrated_cache_hits_wait_for_expiry_before_fallback(
    client, config, omdb, reel, monkeypatch
):
    clock = [1000000]
    monkeypatch.setattr(service.time, "time", lambda: clock[0])
    config.reeldb_api_key = SecretStr("")
    assert (await lookup(client)).json()["results"][0]["rating"] is None
    config.reeldb_api_key = SecretStr("reel-test-key")
    assert (await lookup(client)).json()["results"][0]["rating"] is None
    assert (len(omdb[1]), len(reel[1])) == (1, 0)
    clock[0] += service.CACHE_TTL
    assert (await lookup(client)).json()["results"][0]["rating"]["votes"] == 4477
    assert (len(omdb[1]), len(reel[1])) == (2, 1)


def prime(title="Unrated"):
    return {
        "request_id": "1",
        "provider": "primevideo",
        "provider_id": "B000000001",
        "title": title,
    }


async def test_second_provider_reuses_fallback_ratings_without_reeldb(client, omdb, reel):
    await lookup(client)
    response = await client.post("/v1/resolve", json={"cards": [prime()]})
    assert response.json()["results"][0]["rating"]["votes"] == 4477
    assert (len(omdb[1]), len(reel[1])) == (2, 1)


async def test_batch_calls_reeldb_once_per_imdb_id(client, omdb, reel):
    cards = [{"request_id": "0", "netflix_id": "123", "title": "Unrated"}, prime()]
    response = await client.post("/v1/resolve", json={"cards": cards})
    assert [result["rating"]["votes"] for result in response.json()["results"]] == [4477, 4477]
    assert (len(omdb[1]), len(reel[1])) == (1, 1)


async def test_stale_refresh_keeps_stored_fallback_ratings(client, config, omdb, reel, monkeypatch):
    clock = [1000000]
    monkeypatch.setattr(service.time, "time", lambda: clock[0])
    await lookup(client)
    clock[0] += service.CACHE_TTL
    assert (await lookup(client)).json()["results"][0]["rating"]["votes"] == 4477
    assert (len(omdb[1]), len(reel[1])) == (2, 1)
    with operations_session(config.database_url.get_secret_value()) as db:
        assert db.get(IMDbCache, "tt6").fetched_at == clock[0]


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
async def test_invalid_fallback_is_private_and_leaves_cache_unchanged(
    client, config, reel, changes
):
    reel[0].update(changes)
    response = await lookup(client)
    assert response.status_code == 503
    assert response.json() == {"detail": "Ratings unavailable"}
    assert "reel-test-key" not in response.text
    with operations_session(config.database_url.get_secret_value()) as db:
        assert db.get(IMDbCache, "tt6") is None
        assert db.get(ProviderMapping, ("netflix", "123")) is None


@pytest.mark.parametrize("status", [403, 429, 500])
async def test_fallback_http_errors_are_retryable(client, reel, monkeypatch, status, caplog):
    original = httpx.Client.get

    def get(self, url, *, params):
        if url == ReelDBRatingsProvider.endpoint:
            return httpx.Response(status, request=httpx.Request("GET", url, params=params))
        return original(self, url, params=params)

    monkeypatch.setattr(httpx.Client, "get", get)
    assert (await lookup(client)).status_code == 503
    assert f"ReelDB failed: imdb_id='tt6' reason=HTTP {status}" in caplog.messages
    assert "reel-test-key" not in caplog.text
    assert "apikey=" not in caplog.text


@pytest.mark.parametrize("provider", [OMDbRatingsProvider, ReelDBRatingsProvider])
def test_ratings_provider_contract(provider, monkeypatch):
    def respond(request):
        assert request.url.params["i"] == "tt6"
        return httpx.Response(200, json=payload(), request=request)

    def get(self, url, *, params):
        return respond(httpx.Request("GET", url, params=params))

    monkeypatch.setattr(httpx.Client, "get", get)
    with httpx.Client() as client:
        result = provider(client, SecretStr("test")).fetch(RatingsProviderRequest(imdb_id="tt6"))
    assert isinstance(result, RatingsProviderResult)
    assert result.votes == 4477
    with pytest.raises(ValidationError):
        RatingsProviderRequest()


async def test_two_providers_receive_and_cache_fallback_ratings(client, reel):
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
    assert 1 <= len(reel[1]) <= 2
    calls = len(reel[1])
    assert (await lookup(client)).json()["results"][0]["rating"]["votes"] == 4477
    assert len(reel[1]) == calls


async def test_fallback_timeout_is_retryable(client, reel, monkeypatch):
    original = httpx.Client.get

    def get(self, url, *, params):
        if url == ReelDBRatingsProvider.endpoint:
            raise httpx.ReadTimeout("upstream timeout")
        return original(self, url, params=params)

    monkeypatch.setattr(httpx.Client, "get", get)
    assert (await lookup(client)).status_code == 503


async def test_reeldb_http_400_not_found_keeps_batch_available(client, reel, monkeypatch, caplog):
    original = httpx.Client.get

    def get(self, url, *, params):
        if url == ReelDBRatingsProvider.endpoint:
            return httpx.Response(
                400,
                json={"Response": "False", "Error": "Movie not found!"},
                request=httpx.Request("GET", url, params=params),
            )
        return original(self, url, params=params)

    monkeypatch.setattr(httpx.Client, "get", get)
    response = await client.post(
        "/v1/resolve",
        json={
            "cards": [
                {"request_id": "0", "netflix_id": "123", "title": "Unrated"},
                {"request_id": "1", "netflix_id": "456", "title": "Same Name"},
            ]
        },
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["status"] == "not_found"
    assert results[1]["rating"]["imdb_id"] == "tt1"
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


@pytest.mark.parametrize(
    "status,data,reason",
    [
        (400, {"Response": "False", "Error": "Invalid API key!"}, "HTTP 400"),
        (500, {"Response": "False", "Error": "Movie not found!"}, "HTTP 500"),
        (200, {"Response": "False", "Error": "Invalid API key!"}, "Invalid API key"),
        (200, {"Response": "False", "Error": "Request limit reached!"}, "Request limit reached"),
        (200, {"Response": "False", "Error": "reel-test-key"}, "Upstream rejected request"),
        (200, payload(imdbRating="reel-test-key"), "ValidationError"),
        (200, {}, "Invalid response: missing or non-string fields"),
    ],
)
async def test_provider_failure_logs_are_useful_and_private(
    client, reel, monkeypatch, caplog, status, data, reason
):
    original = httpx.Client.get

    def get(self, url, *, params):
        if url == ReelDBRatingsProvider.endpoint:
            return httpx.Response(
                status, json=data, request=httpx.Request("GET", url, params=params)
            )
        return original(self, url, params=params)

    monkeypatch.setattr(httpx.Client, "get", get)
    response = await lookup(client)
    assert response.status_code == 503
    assert response.json() == {"detail": "Ratings unavailable"}
    assert f"ReelDB failed: imdb_id='tt6' reason={reason}" in caplog.messages
    assert any("Resolve failed: cards=1 error=" in m for m in caplog.messages)
    assert "ratings_providers.py" in caplog.text
    assert "reel-test-key" not in caplog.text
    assert "apikey=" not in caplog.text
