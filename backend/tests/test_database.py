"""Database transactions and schema checks against isolated test databases."""

import sqlite3

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from src.catalogue.models import IMDbCache, ProviderMapping
from src.catalogue.schemas import Card
from src.catalogue.service import resolve
from src.database import database_engine, operations_session
from src.main import create_app


def test_postgres_tables_are_schema_qualified():
    for model in (ProviderMapping, IMDbCache):
        ddl = str(CreateTable(model.__table__).compile(dialect=postgresql.dialect()))
        assert f"CREATE TABLE watchsift.{model.__tablename__}" in ddl


def test_operations_rollback_on_error(config):
    with pytest.raises(RuntimeError, match="cancel"):
        with operations_session(config.database_url.get_secret_value()) as db:
            db.add(ProviderMapping(provider="netflix", provider_id="rollback", imdb_id="tt1"))
            db.flush()
            raise RuntimeError("cancel")
    with operations_session(config.database_url.get_secret_value()) as db:
        assert db.get(ProviderMapping, ("netflix", "rollback")) is None


async def test_database_errors_keep_lookup_response_private(config, database_path):
    with sqlite3.connect(database_path) as db:
        db.execute("DROP TABLE provider_mapping")
    async with AsyncClient(
        transport=ASGITransport(app=create_app(config)), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/resolve",
            json={"cards": [{"request_id": "0", "netflix_id": "123", "title": "Sensitive title"}]},
        )
    assert response.status_code == 503
    assert response.json() == {"detail": "Ratings unavailable"}
    assert response.headers["retry-after"] == "30"


def test_mapping_correction_is_visible_to_later_cards_in_same_batch(config):
    def card(year=None, kind=None):
        return Card(request_id="0", netflix_id="123", title="Same Name", year=year, type=kind)

    resolve(config, [card(2020, "movie")])
    results = resolve(config, [card(2021, "movie"), card()]).results
    assert [result.rating.imdb_id for result in results] == ["tt2", "tt2"]


def test_missing_or_unsupported_database_url_is_rejected():
    for url in ("", "mysql://localhost/watchsift"):
        with pytest.raises(ValueError):
            database_engine(url)
