import gzip
import sqlite3

import pytest

from src.catalogue.importer import import_catalogue
from src.catalogue.manage import rollback
from src.catalogue.schemas import Card
from src.catalogue.service import resolve
from src.catalogue.utils import normalize_title, title_variants


def card(title, **kwargs):
    return Card(request_id="0", netflix_id="123", title=title, **kwargs)


@pytest.mark.parametrize(
    "title,year,kind,status",
    [
        ("Same Name", None, None, "ambiguous"),
        ("Same Name", 2020, None, "ambiguous"),
        ("Same Name", 2020, "movie", "matched"),
        ("Same Name", 2020, "series", "matched"),
        ("Same Name", 2019, "movie", "not_found"),
        ("Alternate Title", None, None, "matched"),
        ("Kumbalangi Nights", None, None, "matched"),
        ("കുമ്പളങ്ങി നൈറ്റ്സ്", None, None, "matched"),
        ("Unrated", None, None, "not_found"),
        ("Only Rated Alias", None, None, "matched"),
        ("Episode", None, None, "not_found"),
        ("Papa Yaar by Zakir Khan", None, "movie", "matched"),
        ("Papa Yaar by Zakir Khan", None, "series", "matched"),
    ],
)
def test_conservative_matching(config, title, year, kind, status):
    result = resolve(config.data_dir, [card(title, year=year, type=kind)]).results[0]
    assert result.status == status
    if status != "matched":
        assert result.rating is None


def test_normalization_preserves_scripts_and_combining_marks():
    assert normalize_title(" Ａ Film—Name! ") == "a film name"
    assert normalize_title("കുമ്പളങ്ങി നൈറ്റ്സ്") == "കുമ്പളങ്ങി നൈറ്റ്സ്"
    assert normalize_title("Straße") == "strasse"


@pytest.mark.parametrize(
    "leader,runner,status",
    [
        (1000, 10, "matched"),
        (1000, 11, "ambiguous"),
        (999, 1, "ambiguous"),
        (1000, None, "matched"),
    ],
)
def test_popularity_requires_minimum_votes_and_clear_dominance(config, leader, runner, status):
    with sqlite3.connect(config.data_dir / "current.sqlite3") as db:
        db.execute("UPDATE title SET votes=? WHERE imdb_id='tt1'", (leader,))
        db.execute(
            "UPDATE title SET votes=?, rating=? WHERE imdb_id='tt2'",
            (runner, 8.0 if runner is not None else None),
        )
    result = resolve(config.data_dir, [card("Same Name", type="movie")]).results[0]
    assert result.status == status
    assert (result.rating.imdb_id if result.rating else None) == (
        "tt1" if status == "matched" else None
    )
    assert resolve(config.data_dir, [card("Same Name", year=2021, type="movie")]).results[
        0
    ].status == ("matched" if runner is not None else "not_found")


def test_primary_title_beats_a_conflicting_alias_and_preserves_hashtags(config):
    with sqlite3.connect(config.data_dir / "current.sqlite3") as db:
        db.execute(
            "UPDATE title SET primary_title='#Love', rating=5.7, votes=185 WHERE imdb_id='tt1'"
        )
        db.execute(
            "UPDATE title SET primary_title='Love', rating=7.6, votes=48939 WHERE imdb_id='tt2'"
        )
        db.executemany("INSERT INTO alias VALUES ('love', ?)", [("tt1",), ("tt2",)])
    assert resolve(config.data_dir, [card("#Love")]).results[0].rating.imdb_id == "tt1"
    assert resolve(config.data_dir, [card("Love")]).results[0].rating.imdb_id == "tt2"


def test_unrated_primary_namesake_blocks_a_popular_older_title(config):
    with sqlite3.connect(config.data_dir / "current.sqlite3") as db:
        db.execute("UPDATE title SET primary_title='Epic', votes=100000 WHERE imdb_id='tt1'")
        db.execute("UPDATE title SET primary_title='Epic' WHERE imdb_id='tt6'")
        db.execute(
            "UPDATE title SET primary_title='Different Film', votes=2000 WHERE imdb_id='tt2'"
        )
        db.executemany("INSERT INTO alias VALUES ('epic', ?)", [("tt1",), ("tt2",), ("tt6",)])
    assert resolve(config.data_dir, [card("Epic")]).results[0].status == "ambiguous"


def test_limited_variants_preserve_indian_marks_and_sequel_numbers():
    assert "Romanchakam" in title_variants("Romã\u200bnchakam")
    assert title_variants("കുമ്പളങ്ങി നൈറ്റ്സ്") == []
    assert title_variants("Rocky II") == []
    assert title_variants("A Quiet Place: Day One") == []
    assert "Operation Safed Sagar" in title_variants(
        "Operation Safed Sagar: The Untold Story of the Kargil War"
    )


def test_unique_fallback_matches_and_conflicting_fallbacks_remain_unknown(config):
    assert (
        resolve(config.data_dir, [card("Kumbalangi Nights I")]).results[0].rating.imdb_id == "tt5"
    )
    with sqlite3.connect(config.data_dir / "current.sqlite3") as db:
        db.execute("INSERT INTO alias VALUES ('operation safed sagar', 'tt1')")
        db.execute("INSERT INTO alias VALUES ('operation safed sagar a documentary', 'tt2')")
    assert (
        resolve(config.data_dir, [card("Operation Safed Sagar: A Documentary")])
        .results[0]
        .rating.imdb_id
        == "tt2"
    )
    assert resolve(config.data_dir, [card("Same Name I")]).results[0].status == "ambiguous"
    assert (
        resolve(config.data_dir, [card("Kumbalangi Nights I", year=2020)]).results[0].status
        == "not_found"
    )


def test_snapshot_replacement_and_rollback(config, source):
    previous = (config.data_dir / "current.sqlite3").resolve()
    replacement = import_catalogue(source, config.data_dir, "2026-10-12")
    assert replacement != previous
    assert (config.data_dir / "previous.sqlite3").resolve() == previous
    rollback(config.data_dir)
    assert (config.data_dir / "current.sqlite3").resolve() == previous
    with sqlite3.connect(previous) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_failed_import_preserves_active_catalogue(config, source):
    current = (config.data_dir / "current.sqlite3").resolve()
    with gzip.open(source / "title.ratings.tsv.gz", "wt") as stream:
        stream.write("tconst\taverageRating\tnumVotes\n")
    with pytest.raises(ValueError, match="empty"):
        import_catalogue(source, config.data_dir, "2026-10-12")
    assert (config.data_dir / "current.sqlite3").resolve() == current
    assert not list(config.data_dir.glob("*.building"))


async def test_resolve_and_validation(client):
    response = await client.post(
        "/v1/resolve", json={"cards": [card("Alternate Title").model_dump()]}
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["rating"] == {
        "imdb_id": "tt1",
        "rating": 7.0,
        "votes": 1000,
    }
    response = await client.post(
        "/v1/resolve", json={"cards": [card("Alternate Title").model_dump()] * 51}
    )
    assert response.status_code == 422
    assert "Alternate Title" not in response.text
    assert (await client.get("/health")).status_code == 200


async def test_oversize_request(client):
    response = await client.post("/v1/resolve", content=b" " * 65537)
    assert response.status_code == 413


def test_shared_mapping_reuses_identity_but_reads_current_rating(config):
    assert (
        resolve(config.data_dir, [card("Same Name", year=2020, type="movie")])
        .results[0]
        .rating.imdb_id
        == "tt1"
    )
    with sqlite3.connect(config.data_dir / "operations.sqlite3") as db:
        assert db.execute("SELECT * FROM provider_mapping").fetchall() == [
            ("netflix", "123", "tt1")
        ]
    with sqlite3.connect(config.data_dir / "current.sqlite3") as db:
        db.execute("UPDATE title SET rating=7.9, votes=2000 WHERE imdb_id='tt1'")
    # A fresh request without the year is ambiguous without the shared mapping.
    assert (
        resolve(config.data_dir, [card("Same Name")], use_mappings=False).results[0].status
        == "ambiguous"
    )
    rating = resolve(config.data_dir, [card("Same Name")]).results[0].rating
    assert (rating.imdb_id, rating.rating, rating.votes) == ("tt1", 7.9, 2000)


def test_mapping_respects_provider_title_and_new_metadata(config):
    resolve(config.data_dir, [card("Same Name", year=2020, type="movie")])
    other = Card(request_id="1", provider="other", provider_id="123", title="Same Name")
    assert resolve(config.data_dir, [other]).results[0].status == "ambiguous"
    assert resolve(config.data_dir, [card("Unrated")]).results[0].rating is None
    assert (
        resolve(config.data_dir, [card("Same Name", year=2021, type="movie")])
        .results[0]
        .rating.imdb_id
        == "tt2"
    )
    assert resolve(config.data_dir, [card("Same Name")]).results[0].rating.imdb_id == "tt2"
    with sqlite3.connect(config.data_dir / "current.sqlite3") as db:
        db.execute("DELETE FROM alias WHERE imdb_id='tt2'")
        db.execute("DELETE FROM title WHERE imdb_id='tt2'")
    assert resolve(config.data_dir, [card("Same Name")]).results[0].status == "ambiguous"


def test_does_not_share_title_only_or_ambiguous_matches(config):
    resolve(config.data_dir, [card("Alternate Title")])
    resolve(config.data_dir, [card("Same Name", year=2020)])
    with sqlite3.connect(config.data_dir / "operations.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM provider_mapping").fetchone()[0] == 0


async def test_generic_provider_identity_and_conflicts(client):
    payload = {
        "request_id": "0",
        "provider": "other",
        "provider_id": "film:123",
        "title": "Same Name",
        "year": 2020,
        "type": "movie",
    }
    response = await client.post("/v1/resolve", json={"cards": [payload]})
    assert response.status_code == 200
    payload.pop("year")
    payload.pop("type")
    assert (await client.post("/v1/resolve", json={"cards": [payload]})).json()["results"][0][
        "rating"
    ]["imdb_id"] == "tt1"
    payload["netflix_id"] = "123"
    assert (await client.post("/v1/resolve", json={"cards": [payload]})).status_code == 422
    payload.pop("netflix_id")
    payload["provider"] = "netflix"
    assert (await client.post("/v1/resolve", json={"cards": [payload]})).status_code == 422


def test_mapping_survives_catalogue_replacement(config, source):
    resolve(config.data_dir, [card("Same Name", year=2020, type="movie")])
    import_catalogue(source, config.data_dir, "2026-10-12")
    assert resolve(config.data_dir, [card("Same Name")]).results[0].rating.imdb_id == "tt1"
    with sqlite3.connect(config.data_dir / "operations.sqlite3") as db:
        assert db.execute("SELECT * FROM provider_mapping").fetchall() == [
            ("netflix", "123", "tt1")
        ]


def test_year_and_type_qualified_dominant_match_is_shared(config):
    with sqlite3.connect(config.data_dir / "current.sqlite3") as db:
        db.execute("UPDATE title SET year=2020, votes=NULL, rating=NULL WHERE imdb_id='tt2'")
    learned = resolve(config.data_dir, [card("Same Name", year=2020, type="movie")])
    assert learned.results[0].rating.imdb_id == "tt1"
    with sqlite3.connect(config.data_dir / "operations.sqlite3") as db:
        assert db.execute("SELECT * FROM provider_mapping").fetchall() == [
            ("netflix", "123", "tt1")
        ]
    assert resolve(config.data_dir, [card("Same Name")]).results[0].rating.imdb_id == "tt1"


def test_dominant_match_without_year_or_type_is_not_shared(config):
    with sqlite3.connect(config.data_dir / "current.sqlite3") as db:
        db.execute("UPDATE title SET year=2020, votes=1 WHERE imdb_id='tt2'")
        db.execute("UPDATE title SET year=2020, votes=1 WHERE imdb_id='tt3'")
    assert (
        resolve(config.data_dir, [card("Same Name", type="movie")]).results[0].status == "matched"
    )
    assert resolve(config.data_dir, [card("Same Name", year=2020)]).results[0].status == "matched"
    with sqlite3.connect(config.data_dir / "operations.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM provider_mapping").fetchone()[0] == 0


def test_compact_acronym_matches_dotted_title_only_when_unique(config):
    assert "G.D.N" in title_variants("GDN")
    assert title_variants("Gdn") == []
    with sqlite3.connect(config.data_dir / "current.sqlite3") as db:
        db.execute("INSERT INTO alias VALUES ('g d n', 'tt1')")
    assert resolve(config.data_dir, [card("GDN")]).results[0].rating.imdb_id == "tt1"
    with sqlite3.connect(config.data_dir / "current.sqlite3") as db:
        db.execute("INSERT INTO alias VALUES ('g d n', 'tt2')")
        db.execute("UPDATE title SET votes=1 WHERE imdb_id='tt2'")
    assert resolve(config.data_dir, [card("GDN")]).results[0].status == "ambiguous"
