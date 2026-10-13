"""All catalogue database access. Callers own the session and transaction."""

from sqlalchemy import tuple_
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session, select

from src.catalogue.constants import CACHE_TTL
from src.catalogue.models import IMDbCache, ProviderMapping

ProviderKey = tuple[str, str]
Known = tuple[ProviderMapping, IMDbCache | None]


def get_known(db: Session, keys: list[ProviderKey]) -> dict[ProviderKey, Known]:
    """Mappings for the given provider identities, each with its cached IMDb row if any."""
    rows = db.exec(
        select(ProviderMapping, IMDbCache)
        .outerjoin(IMDbCache, ProviderMapping.imdb_id == IMDbCache.imdb_id)
        .where(tuple_(ProviderMapping.provider, ProviderMapping.provider_id).in_(keys))
    ).all()
    return {(mapping.provider, mapping.provider_id): (mapping, row) for mapping, row in rows}


def get_cached(db: Session, imdb_ids: set[str]) -> dict[str, IMDbCache]:
    if not imdb_ids:
        return {}
    rows = db.exec(select(IMDbCache).where(IMDbCache.imdb_id.in_(imdb_ids))).all()
    return {row.imdb_id: row for row in rows}


def save(db: Session, records: list[IMDbCache | ProviderMapping]) -> None:
    """Upsert records; concurrent requests may write the same keys."""
    insert = postgres_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    for record in records:
        values = record.model_dump()
        keys = [column.name for column in record.__table__.primary_key]
        statement = insert(type(record)).values(**values)
        guard = None
        if isinstance(record, IMDbCache) and (record.rating is None or record.votes is None):
            # A late unrated response must not erase another request's fresh ratings.
            guard = (
                (IMDbCache.fetched_at + CACHE_TTL <= statement.excluded.fetched_at)
                | IMDbCache.rating.is_(None)
                | IMDbCache.votes.is_(None)
            )
        updates = {key: statement.excluded[key] for key in values if key not in keys}
        db.exec(statement.on_conflict_do_update(index_elements=keys, set_=updates, where=guard))
