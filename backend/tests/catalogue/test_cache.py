import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from src.catalogue import service
from src.catalogue.models import IMDbCache, ProviderMapping
from src.catalogue.schemas import Card
from src.database import operations_session


def card(**kwargs):
    return Card(request_id="0", provider="netflix", provider_id="123", title="Same Name", **kwargs)


def test_cache_survives_new_app_settings_and_needs_no_key_on_hit(config, omdb):
    service.resolve(config, [card()])
    restarted = config.model_copy(update={"omdb_api_key": SecretStr("")})
    assert service.resolve(restarted, [card()]).results[0].rating.votes == 1000
    assert len(omdb[1]) == 1


def test_expiry_is_from_fetch_not_last_read(config, omdb, monkeypatch):
    clock = [1000000]
    monkeypatch.setattr(service.time, "time", lambda: clock[0])
    service.resolve(config, [card()])
    clock[0] += service.CACHE_TTL - 1
    service.resolve(config, [card()])
    assert len(omdb[1]) == 1
    with operations_session(config.database_url.get_secret_value()) as db:
        assert db.get(IMDbCache, "tt1").fetched_at == 1000000
    clock[0] += 1
    omdb[0]["tt1"].update(imdbRating="7.9", imdbVotes="2,000")
    assert service.resolve(config, [card()]).results[0].rating.votes == 2000
    assert omdb[1][-1] == {"apikey": "test-key", "i": "tt1"}


def test_two_providers_share_one_rating_cache_and_refresh(config, omdb, monkeypatch):
    clock = [1000000]
    monkeypatch.setattr(service.time, "time", lambda: clock[0])
    prime = Card(request_id="1", provider="primevideo", provider_id="B000000001", title="Same Name")
    service.resolve(config, [card()])
    clock[0] += 10
    service.resolve(config, [prime])
    with operations_session(config.database_url.get_secret_value()) as db:
        assert len(db.exec(select(ProviderMapping)).all()) == 2
        rows = db.exec(select(IMDbCache)).all()
        assert len(rows) == 1
        assert rows[0].fetched_at == 1000000
    omdb[1].clear()
    service.resolve(config, [prime, card()])
    assert omdb[1] == []
    clock[0] = 1000000 + service.CACHE_TTL
    service.resolve(config, [prime, card()])
    assert omdb[1] == [{"apikey": "test-key", "i": "tt1"}]


def test_concurrent_users_fetch_same_provider_id_once(config, omdb):
    barrier = Barrier(6)

    def request(_):
        barrier.wait(timeout=5)
        return service.resolve(config, [card()]).results[0].rating.imdb_id

    with ThreadPoolExecutor(max_workers=6) as pool:
        assert list(pool.map(request, range(6))) == ["tt1"] * 6
    assert len(omdb[1]) == 1


def test_new_hints_and_changed_titles_correct_mapping(config, omdb):
    service.resolve(config, [card()])
    assert service.resolve(config, [card(year=2021)]).results[0].rating.imdb_id == "tt2"
    assert (
        service.resolve(config, [card(year=2020, type="series")]).results[0].rating.imdb_id == "tt3"
    )
    changed = card().model_copy(update={"title": "Kumbalangi Nights", "type": "movie"})
    assert service.resolve(config, [changed]).results[0].rating.imdb_id == "tt5"
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
    service.resolve(config, [alias])
    assert service.resolve(config, [alias]).results[0].rating.imdb_id == "tt1"
    assert len(omdb[1]) == 1


def test_valid_unrated_titles_are_cached_but_unknowns_are_not(config, omdb):
    unrated = card().model_copy(update={"title": "Unrated"})
    assert service.resolve(config, [unrated]).results[0].rating is None
    assert service.resolve(config, [unrated]).results[0].rating is None
    assert len(omdb[1]) == 1
    with operations_session(config.database_url.get_secret_value()) as db:
        cached = db.get(IMDbCache, "tt6")
        assert (cached.rating, cached.votes) == (None, None)
    unknown = card().model_copy(
        update={"provider_id": "999", "netflix_id": "999", "title": "Unknown"}
    )
    service.resolve(config, [unknown])
    service.resolve(config, [unknown])
    assert len(omdb[1]) == 3
    with operations_session(config.database_url.get_secret_value()) as db:
        assert db.get(ProviderMapping, ("netflix", "999")) is None


@pytest.mark.parametrize("failure", ["network", "quota", "malformed"])
def test_failed_refresh_preserves_cache_and_mapping(config, monkeypatch, failure, database_path):
    service.resolve(config, [card()])
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
        service.resolve(config, [card()])
    with sqlite3.connect(database_path) as db:
        assert db.execute("SELECT * FROM imdb_cache").fetchall() == before
        assert db.execute("SELECT * FROM provider_mapping").fetchall() == mappings


def test_evaluation_bypasses_persistent_cache_and_does_not_change_mappings(config, omdb):
    service.resolve(config, [card(year=2021)])
    assert service.resolve(config, [card()], use_mappings=False).results[0].rating.imdb_id == "tt1"
    assert service.resolve(config, [card()]).results[0].rating.imdb_id == "tt2"
    assert len(omdb[1]) == 2


def test_mapping_and_cache_write_roll_back_together(config, database_path):
    with sqlite3.connect(database_path) as db:
        db.executescript("""
            CREATE TRIGGER reject_mapping BEFORE INSERT ON provider_mapping
            BEGIN SELECT RAISE(ABORT, 'reject mapping'); END;
        """)
    with pytest.raises(IntegrityError, match="reject mapping"):
        service.resolve(config, [card()])
    with operations_session(config.database_url.get_secret_value()) as db:
        assert db.get(IMDbCache, "tt1") is None
        assert db.get(ProviderMapping, ("netflix", "123")) is None
