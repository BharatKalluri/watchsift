from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session

from src.catalogue.models import IMDbCache, ProviderMapping

CACHE_TTL = 7 * 24 * 60 * 60


def _load_card(db: Session, card):
    mapping = db.get(ProviderMapping, (card.provider, card.provider_id))
    row = db.get(IMDbCache, mapping.imdb_id) if mapping else None
    return card, mapping, row


def load(db: Session, cards):
    return [_load_card(db, card) for card in cards]


def save(db: Session, records):
    if not records:
        return
    insert = postgres_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    for record in records:
        if record is None:
            continue
        values = record.model_dump()
        keys = [column.name for column in record.__table__.primary_key]
        statement = insert(type(record)).values(**values)
        condition = None
        if isinstance(record, IMDbCache) and (record.rating is None or record.votes is None):
            # A late unrated response must not erase another request's fresh ratings.
            condition = (
                (IMDbCache.fetched_at + CACHE_TTL <= statement.excluded.fetched_at)
                | IMDbCache.rating.is_(None)
                | IMDbCache.votes.is_(None)
            )
        db.exec(
            statement.on_conflict_do_update(
                index_elements=keys,
                set_={key: statement.excluded[key] for key in values if key not in keys},
                where=condition,
            )
        )
