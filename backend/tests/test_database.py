"""SQLModel migration checks against independent SQLite readers and legacy files."""

import csv
import gzip
import sqlite3

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlmodel import SQLModel, select, text

from src.catalogue.importer import import_catalogue
from src.catalogue.models import Metadata, ProviderMapping, Title
from src.catalogue.schemas import Card
from src.catalogue.service import resolve
from src.database import catalogue_connection, init_operations, operations_session
from src.main import create_app


@pytest.mark.parametrize("identity", ["netflix_id", "provider_id"])
def test_upgrade_removes_telemetry_and_preserves_mappings(config, tmp_path, identity):
    data = tmp_path / "legacy"
    data.mkdir()
    (data / "current.sqlite3").symlink_to((config.data_dir / "current.sqlite3").resolve())
    with sqlite3.connect(data / "operations.sqlite3") as db:
        db.executescript(f"""
            CREATE TABLE provider_mapping (provider TEXT NOT NULL, provider_id TEXT NOT NULL,
                imdb_id TEXT NOT NULL, PRIMARY KEY (provider, provider_id));
            CREATE TABLE metric (count INTEGER);
            CREATE TABLE metric_receipt (batch_id TEXT);
            CREATE TABLE unmatched (title TEXT, {identity} TEXT);
            CREATE TABLE unmatched_legacy (title TEXT);
            INSERT INTO provider_mapping VALUES ('netflix', '123', 'tt1');
            INSERT INTO provider_mapping VALUES ('primevideo', 'B000000001', 'tt2');
            INSERT INTO metric VALUES (42);
            INSERT INTO metric_receipt VALUES ('old-batch');
            INSERT INTO unmatched VALUES ('Old report', '456');
            INSERT INTO unmatched_legacy VALUES ('Older report');
        """)
    init_operations(data)
    init_operations(data)
    with sqlite3.connect(data / "operations.sqlite3") as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [
            ("provider_mapping",)
        ]
        assert db.execute("SELECT * FROM provider_mapping ORDER BY provider").fetchall() == [
            ("netflix", "123", "tt1"),
            ("primevideo", "B000000001", "tt2"),
        ]
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    result = resolve(data, [Card(request_id="0", netflix_id="123", title="Same Name")])
    assert result.results[0].rating.imdb_id == "tt1"


def test_catalogue_sessions_are_readonly_and_keep_open_snapshot(config, source):
    with catalogue_connection(config.data_dir) as db:
        original = db.get(Metadata, "version").value
        replacement = import_catalogue(source, config.data_dir, "2026-10-12")
        assert db.exec(select(Metadata.value).where(Metadata.key == "version")).one() == original
        with catalogue_connection(config.data_dir) as fresh:
            assert fresh.get(Metadata, "version").value == replacement.stem.removeprefix(
                "catalogue-"
            )
    with catalogue_connection(config.data_dir) as db:
        with pytest.raises(OperationalError, match="readonly"):
            db.execute(text("DELETE FROM title"))


def test_operations_rollback_on_error(config):
    with pytest.raises(RuntimeError, match="cancel"):
        with operations_session(config.data_dir) as db:
            db.add(ProviderMapping(provider="netflix", provider_id="rollback", imdb_id="tt1"))
            db.flush()
            raise RuntimeError("cancel")
    with operations_session(config.data_dir) as db:
        assert db.get(ProviderMapping, ("netflix", "rollback")) is None


def test_bulk_import_includes_last_batch_and_null_ratings(config, source):
    with gzip.open(source / "title.basics.tsv.gz", "wt", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", quoting=csv.QUOTE_NONE)
        writer.writerow(["tconst", "titleType", "primaryTitle", "originalTitle", "startYear"])
        writer.writerows(
            [f"tt{i}", "movie", f"Bulk {i}", f"Bulk {i}", "2020"] for i in range(1, 10002)
        )
    import_catalogue(source, config.data_dir, "2026-10-12")
    with sqlite3.connect(config.data_dir / "current.sqlite3") as db:
        assert db.execute("SELECT count(*) FROM title").fetchone()[0] == 10001
        assert db.execute("SELECT rating, votes FROM title WHERE imdb_id='tt10001'").fetchone() == (
            None,
            None,
        )
        assert (
            db.execute("SELECT count(*) FROM alias WHERE normalized='bulk 10001'").fetchone()[0]
            == 1
        )
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    with catalogue_connection(config.data_dir) as db:
        assert db.get(Title, "tt1").rating == 7.0


@pytest.mark.parametrize("rating,votes", [(11, 1000), (7, -1)])
def test_import_checks_constraints_and_preserves_active_snapshot(config, source, rating, votes):
    original = (config.data_dir / "current.sqlite3").resolve()
    with gzip.open(source / "title.ratings.tsv.gz", "wt") as stream:
        stream.write(f"tconst\taverageRating\tnumVotes\ntt1\t{rating}\t{votes}\n")
    with pytest.raises(IntegrityError):
        import_catalogue(source, config.data_dir, "2026-10-12")
    assert (config.data_dir / "current.sqlite3").resolve() == original
    assert not list(config.data_dir.glob("*.building"))


async def test_database_errors_keep_lookup_response_private(config):
    with sqlite3.connect(config.data_dir / "operations.sqlite3") as db:
        db.execute("DROP TABLE provider_mapping")
    async with AsyncClient(
        transport=ASGITransport(app=create_app(config)), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/resolve",
            json={"cards": [{"request_id": "0", "netflix_id": "123", "title": "Sensitive title"}]},
        )
    assert response.status_code == 503
    assert response.json() == {"detail": "Catalogue unavailable"}
    assert response.headers["retry-after"] == "30"


def test_mapping_correction_is_visible_to_later_cards_in_same_batch(config):
    def card(year=None, kind=None):
        return Card(request_id="0", netflix_id="123", title="Same Name", year=year, type=kind)

    resolve(config.data_dir, [card(2020, "movie")])
    results = resolve(config.data_dir, [card(2021, "movie"), card()]).results
    assert [result.rating.imdb_id for result in results] == ["tt2", "tt2"]


def test_failed_upgrade_rolls_back_telemetry_removal(tmp_path, monkeypatch):
    data = tmp_path / "failed-upgrade"
    data.mkdir()
    with sqlite3.connect(data / "operations.sqlite3") as db:
        db.execute("CREATE TABLE unmatched (title TEXT)")
        db.execute("INSERT INTO unmatched VALUES ('Old report')")

    def fail(*args, **kwargs):
        raise RuntimeError("mapping creation failed")

    monkeypatch.setattr(SQLModel.metadata, "create_all", fail)
    with pytest.raises(RuntimeError, match="mapping creation failed"):
        init_operations(data)
    with sqlite3.connect(data / "operations.sqlite3") as db:
        assert db.execute("SELECT * FROM unmatched").fetchall() == [("Old report",)]
