import logging
import sqlite3
import time

import httpx
import pytest

from src.catalogue.schemas import Card
from src.catalogue.service import CACHE_TTL, resolve
from src.config import Settings


def card(**kwargs):
    return Card(request_id="0", netflix_id="123", title="Same Name", **kwargs)


def test_omdb_lookup_without_dataset_caches_votes_until_expiry(config, omdb, database_path, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    first = resolve(config, [card(year=2020, type="movie")])
    assert first.results[0].rating.model_dump() == {
        "imdb_id": "tt1",
        "rating": 7.0,
        "votes": 1000,
    }
    assert first.dataset_version == "omdb"
    assert omdb[1][0] == {"apikey": "test-key", "t": "Same Name", "y": "2020", "type": "movie"}
    omdb[0]["tt1"].update(imdbRating="7.9", imdbVotes="2,000")
    assert resolve(config, [card()]).results[0].rating.votes == 1000
    assert len(omdb[1]) == 1
    assert caplog.messages == [
        "OMDb request: title='Same Name' imdb_id=None year=2020 type='movie'"
    ]
    with sqlite3.connect(database_path) as db:
        db.execute("UPDATE imdb_cache SET fetched_at=?", (int(time.time()) - CACHE_TTL,))
    assert resolve(config, [card()]).results[0].rating.votes == 2000
    assert omdb[1][-1]["i"] == "tt1"
    assert caplog.messages[-1] == ("OMDb request: title=None imdb_id='tt1' year=None type=None")
    assert len(caplog.messages) == 2
    assert config.omdb_api_key.get_secret_value() not in caplog.text


def test_duplicates_and_order_and_mapping_correction(config, omdb, database_path):
    other = Card(
        request_id="other",
        provider="primevideo",
        provider_id="B000000001",
        title="Kumbalangi Nights",
    )
    results = resolve(config, [card(year=2020), other, card(year=2021), card()]).results
    assert [r.request_id for r in results] == ["0", "other", "0", "0"]
    assert [r.rating.imdb_id for r in results] == ["tt1", "tt5", "tt2", "tt2"]
    omdb[1].clear()
    resolve(config, [card()] * 3)
    assert len(omdb[1]) == 0
    with sqlite3.connect(database_path) as db:
        assert db.execute(
            "SELECT provider, provider_id, imdb_id FROM provider_mapping ORDER BY provider"
        ).fetchall() == [("netflix", "123", "tt2"), ("primevideo", "B000000001", "tt5")]


@pytest.mark.parametrize("title", ["Unknown", "Unrated"])
async def test_missing_and_unrated_are_not_found(client, title):
    response = await client.post(
        "/v1/resolve",
        json={
            "cards": [
                {
                    "request_id": "0",
                    "netflix_id": "123",
                    "title": title,
                }
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["results"] == [
        {"request_id": "0", "status": "not_found", "rating": None}
    ]


@pytest.mark.parametrize(
    "data",
    [
        {"Response": "False", "Error": "Invalid API key!"},
        {"Response": "False", "Error": "Request limit reached!"},
        {"Response": "True"},
        [],
    ],
)
async def test_bad_upstream_responses_are_private_and_retryable(client, monkeypatch, data):
    monkeypatch.setattr(
        httpx.Client,
        "get",
        lambda *a, **kw: httpx.Response(
            200, json=data, request=httpx.Request("GET", "https://omdb.test/")
        ),
    )
    response = await client.post("/v1/resolve", json={"cards": [card().model_dump()]})
    assert response.status_code == 503
    assert response.json() == {"detail": "Ratings unavailable"}
    assert response.headers["retry-after"] == "30"
    assert "test-key" not in response.text


async def test_network_failure_is_retryable(client, monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")

    def fail(*args, **kwargs):
        raise httpx.ReadTimeout("upstream timeout")

    monkeypatch.setattr(httpx.Client, "get", fail)
    response = await client.post("/v1/resolve", json={"cards": [card().model_dump()]})
    assert response.status_code == 503
    assert caplog.messages == ["OMDb request: title='Same Name' imdb_id=None year=None type=None"]


async def test_missing_key_health_and_lookup(client, config):
    config.omdb_api_key = Settings(OMDB_API_KEY="").omdb_api_key
    assert (await client.get("/health")).status_code == 503
    assert (
        await client.post("/v1/resolve", json={"cards": [card().model_dump()]})
    ).status_code == 503


def test_settings_load_local_key_without_exposing_it(tmp_path, monkeypatch):
    monkeypatch.delenv("OMDB_API_KEY", raising=False)
    local = tmp_path / ".env.local"
    local.write_text("OMDB_API_KEY=local-test-key\n")
    config = Settings(_env_file=local)
    assert config.omdb_api_key.get_secret_value() == "local-test-key"
    assert config.omdb_api_key.get_secret_value() not in repr(config)
