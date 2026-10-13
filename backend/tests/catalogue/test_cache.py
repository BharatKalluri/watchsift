import asyncio
import sqlite3
from threading import Event, Lock, get_ident

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from src.catalogue import cache, service
from src.catalogue.models import IMDbCache, ProviderMapping
from src.catalogue.ratings_providers import OMDbRatingsProvider, ReelDBRatingsProvider
from src.catalogue.schemas import Card
from src.database import operations_session
from tests import resolve


def card(**kwargs):
    return Card(request_id="0", provider="netflix", provider_id="123", title="Same Name", **kwargs)


def test_resolve_card_returns_response_and_writes_without_persisting(config):
    with httpx.Client(timeout=2) as client:
        result, writes = service.resolve_card(
            card(),
            service._lookup(card(), None, None, OMDbRatingsProvider(client, config.omdb_api_key)),
            None,
            ReelDBRatingsProvider(client, config.reeldb_api_key),
        )
    assert result.request_id == "0"
    assert result.status == "matched"
    assert result.rating.imdb_id == "tt1"
    assert [type(record) for record in writes] == [IMDbCache, ProviderMapping]
    with operations_session(config.database_url.get_secret_value()) as db:
        assert db.get(IMDbCache, "tt1") is None
        assert db.get(ProviderMapping, ("netflix", "123")) is None


def test_resolve_uses_caller_thread_and_leaves_commit_to_caller(config, monkeypatch):
    caller = get_ident()
    with pytest.raises(RuntimeError, match="caller rollback"):
        with operations_session(config.database_url.get_secret_value()) as db:
            original_get, original_exec = db.get, db.exec

            def get(*args, **kwargs):
                assert get_ident() == caller
                return original_get(*args, **kwargs)

            def execute(*args, **kwargs):
                assert get_ident() == caller
                return original_exec(*args, **kwargs)

            monkeypatch.setattr(db, "get", get)
            monkeypatch.setattr(db, "exec", execute)
            assert service.resolve(config, [card()], db).results[0].rating.imdb_id == "tt1"
            assert db.get(IMDbCache, "tt1") is not None
            raise RuntimeError("caller rollback")
    with operations_session(config.database_url.get_secret_value()) as db:
        assert db.get(IMDbCache, "tt1") is None
        assert db.get(ProviderMapping, ("netflix", "123")) is None


def test_cache_survives_new_app_settings_and_needs_no_key_on_hit(config, omdb):
    resolve(config, [card()])
    restarted = config.model_copy(update={"omdb_api_key": SecretStr("")})
    assert (resolve(restarted, [card()])).results[0].rating.votes == 1000
    assert len(omdb[1]) == 1


def test_expiry_is_from_fetch_not_last_read(config, omdb, monkeypatch):
    clock = [1000000]
    monkeypatch.setattr(service.time, "time", lambda: clock[0])
    resolve(config, [card()])
    clock[0] += service.CACHE_TTL - 1
    resolve(config, [card()])
    assert len(omdb[1]) == 1
    with operations_session(config.database_url.get_secret_value()) as db:
        assert db.get(IMDbCache, "tt1").fetched_at == 1000000
    clock[0] += 1
    omdb[0]["tt1"].update(imdbRating="7.9", imdbVotes="2,000")
    assert (resolve(config, [card()])).results[0].rating.votes == 2000
    assert omdb[1][-1] == {"apikey": "test-key", "i": "tt1"}


def test_two_providers_share_one_rating_cache_and_refresh(config, omdb, monkeypatch):
    clock = [1000000]
    monkeypatch.setattr(service.time, "time", lambda: clock[0])
    prime = Card(request_id="1", provider="primevideo", provider_id="B000000001", title="Same Name")
    resolve(config, [card()])
    clock[0] += 10
    resolve(config, [prime])
    with operations_session(config.database_url.get_secret_value()) as db:
        assert len(db.exec(select(ProviderMapping)).all()) == 2
        rows = db.exec(select(IMDbCache)).all()
        assert len(rows) == 1
        assert rows[0].fetched_at == 1000000
    omdb[1].clear()
    resolve(config, [prime, card()])
    assert omdb[1] == []
    clock[0] = 1000000 + service.CACHE_TTL
    resolve(config, [prime, card()])
    assert 1 <= len(omdb[1]) <= 2
    assert all(call == {"apikey": "test-key", "i": "tt1"} for call in omdb[1])


async def test_concurrent_cache_misses_are_safe_and_cached(config, omdb):
    async def request(_):
        return (await asyncio.to_thread(resolve, config, [card()])).results[0].rating.imdb_id

    assert await asyncio.gather(*(request(i) for i in range(6))) == ["tt1"] * 6
    assert 1 <= len(omdb[1]) <= 6
    calls = len(omdb[1])
    assert (resolve(config, [card()])).results[0].rating.imdb_id == "tt1"
    assert len(omdb[1]) == calls
    with operations_session(config.database_url.get_secret_value()) as db:
        assert len(db.exec(select(IMDbCache)).all()) == 1
        assert len(db.exec(select(ProviderMapping)).all()) == 1


@pytest.mark.parametrize(
    "age,rating,votes,expected",
    [
        (1, None, None, 7.0),
        (1, None, 100, 7.0),
        (1, 5.0, None, 7.0),
        (1, 5.0, 100, 5.0),
        (service.CACHE_TTL, None, None, None),
    ],
)
def test_late_cache_write_preserves_fresh_ratings(config, age, rating, votes, expected):
    resolve(config, [card()])
    storage = config.database_url.get_secret_value()
    with operations_session(storage) as db:
        row = db.get(IMDbCache, "tt1")
    row.rating, row.votes = rating, votes
    row.fetched_at += age
    with operations_session(storage) as db:
        cache.save(db, [row])
    with operations_session(storage) as db:
        assert db.get(IMDbCache, "tt1").rating == expected


def test_batch_limits_active_provider_requests_to_eight(config, monkeypatch):
    original = httpx.Client.get
    active = peak = 0
    started = Event()
    lock = Lock()

    def get(self, url, *, params):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            if active == 8:
                started.set()
        try:
            assert started.wait(timeout=2)
            return original(self, url, params=params)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(httpx.Client, "get", get)
    cards = [Card(request_id=str(i), netflix_id=str(i), title="Same Name") for i in range(12)]
    response = resolve(config, cards)
    assert peak == 8
    assert [r.request_id for r in response.results] == [str(i) for i in range(12)]
    assert all(r.rating.imdb_id == "tt1" for r in response.results)


async def test_independent_lookups_overlap_and_keep_input_order(client, monkeypatch):
    original = httpx.Client.get
    started = []
    both_started = Event()
    lock = Lock()

    def get(self, url, *, params=None, **kwargs):
        if params and params.get("t") in {"Same Name", "Kumbalangi Nights"}:
            with lock:
                started.append(params["t"])
                if len(started) == 2:
                    both_started.set()
            assert both_started.wait(timeout=2)
        return original(self, url, params=params, **kwargs)

    monkeypatch.setattr(httpx.Client, "get", get)
    response = await client.post(
        "/v1/resolve",
        json={
            "cards": [
                {"request_id": "first", "netflix_id": "123", "title": "Same Name"},
                {"request_id": "second", "netflix_id": "456", "title": "Kumbalangi Nights"},
            ]
        },
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert [r["request_id"] for r in results] == ["first", "second"]
    assert [r["rating"]["imdb_id"] for r in results] == ["tt1", "tt5"]


def test_new_hints_and_changed_titles_correct_mapping(config, omdb):
    resolve(config, [card()])
    assert (resolve(config, [card(year=2021)])).results[0].rating.imdb_id == "tt2"
    assert (resolve(config, [card(year=2020, type="series")])).results[0].rating.imdb_id == "tt3"
    changed = card().model_copy(update={"title": "Kumbalangi Nights", "type": "movie"})
    assert (resolve(config, [changed])).results[0].rating.imdb_id == "tt5"
    with operations_session(config.database_url.get_secret_value()) as db:
        mapping = db.get(ProviderMapping, ("netflix", "123"))
        assert (mapping.imdb_id, mapping.lookup_title, mapping.lookup_type) == (
            "tt5",
            "Kumbalangi Nights",
            "movie",
        )
    assert len(omdb[1]) == 4


def test_alias_lookup_reuses_mapping_even_when_canonical_title_differs(config, omdb):
    alias = card().model_copy(update={"title": "Alternate Title"})
    resolve(config, [alias])
    assert (resolve(config, [alias])).results[0].rating.imdb_id == "tt1"
    assert len(omdb[1]) == 1


def test_valid_unrated_titles_are_cached_but_unknowns_are_not(config, omdb):
    unrated = card().model_copy(update={"title": "Unrated"})
    assert (resolve(config, [unrated])).results[0].rating is None
    assert (resolve(config, [unrated])).results[0].rating is None
    assert len(omdb[1]) == 1
    with operations_session(config.database_url.get_secret_value()) as db:
        cached = db.get(IMDbCache, "tt6")
        assert (cached.rating, cached.votes) == (None, None)
    unknown = card().model_copy(
        update={"provider_id": "999", "netflix_id": "999", "title": "Unknown"}
    )
    resolve(config, [unknown])
    resolve(config, [unknown])
    assert len(omdb[1]) == 3
    with operations_session(config.database_url.get_secret_value()) as db:
        assert db.get(ProviderMapping, ("netflix", "999")) is None


@pytest.mark.parametrize("failure", ["network", "quota", "malformed"])
def test_failed_refresh_preserves_cache_and_mapping(config, monkeypatch, failure, database_path):
    resolve(config, [card()])
    with sqlite3.connect(database_path) as db:
        db.execute("UPDATE imdb_cache SET fetched_at=0")
        before = db.execute("SELECT * FROM imdb_cache").fetchall()
        mappings = db.execute("SELECT * FROM provider_mapping").fetchall()

    def fail(*args, **kwargs):
        if failure == "network":
            raise httpx.ReadTimeout("timeout")
        data = (
            {"Response": "False", "Error": "Request limit reached!"}
            if failure == "quota"
            else {
                "Response": "True",
                "Title": "Invalid",
            }
        )
        return httpx.Response(200, json=data, request=httpx.Request("GET", "https://omdb.test/"))

    monkeypatch.setattr(httpx.Client, "get", fail)
    with pytest.raises((httpx.ReadTimeout, ValueError)):
        resolve(config, [card()])
    with sqlite3.connect(database_path) as db:
        assert db.execute("SELECT * FROM imdb_cache").fetchall() == before
        assert db.execute("SELECT * FROM provider_mapping").fetchall() == mappings


def test_mapping_and_cache_write_roll_back_together(config, database_path):
    with sqlite3.connect(database_path) as db:
        db.executescript("""
            CREATE TRIGGER reject_mapping BEFORE INSERT ON provider_mapping
            BEGIN SELECT RAISE(ABORT, 'reject mapping'); END;
        """)
    with pytest.raises(IntegrityError, match="reject mapping"):
        resolve(config, [card()])
    with operations_session(config.database_url.get_secret_value()) as db:
        assert db.get(IMDbCache, "tt1") is None
        assert db.get(ProviderMapping, ("netflix", "123")) is None


def test_failed_batch_does_not_persist_successful_cards(config, monkeypatch):
    original = OMDbRatingsProvider.fetch

    def fetch(self, request):
        if request.title == "Unknown":
            raise ValueError("provider unavailable")
        return original(self, request)

    monkeypatch.setattr(OMDbRatingsProvider, "fetch", fetch)
    unknown = Card(request_id="1", netflix_id="456", title="Unknown")
    with pytest.raises(ValueError, match="provider unavailable"):
        resolve(config, [card(), unknown])
    with operations_session(config.database_url.get_secret_value()) as db:
        assert db.exec(select(IMDbCache)).all() == []
        assert db.exec(select(ProviderMapping)).all() == []


def test_batch_writes_roll_back_together(config, database_path):
    with sqlite3.connect(database_path) as db:
        db.executescript("""
            CREATE TRIGGER reject_second_mapping BEFORE INSERT ON provider_mapping
            WHEN NEW.provider_id = '456'
            BEGIN SELECT RAISE(ABORT, 'reject second mapping'); END;
        """)
    other = Card(request_id="1", netflix_id="456", title="Kumbalangi Nights")
    with pytest.raises(IntegrityError, match="reject second mapping"):
        resolve(config, [card(), other])
    with operations_session(config.database_url.get_secret_value()) as db:
        assert db.exec(select(IMDbCache)).all() == []
        assert db.exec(select(ProviderMapping)).all() == []
