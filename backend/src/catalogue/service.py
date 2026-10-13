import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import httpx
from sqlmodel import Session

from src.catalogue import cache, constants, schemas, utils
from src.catalogue.cache import CACHE_TTL
from src.catalogue.models import IMDbCache, ProviderMapping
from src.catalogue.ratings_providers import (
    OMDbRatingsProvider,
    RatingsProvider,
    ReelDBRatingsProvider,
)
from src.config import Settings


def matches(row: IMDbCache, card: schemas.Card, lookup_title: str | None = None) -> bool:
    return (
        utils.title_identity(card.title)
        in {utils.title_identity(row.title), utils.title_identity(lookup_title or row.title)}
        and (card.year is None or card.year == row.year)
        and (card.type is None or card.type == row.type)
    )


def _fetch(provider: RatingsProvider, **hints) -> IMDbCache | None:
    request = schemas.RatingsProviderRequest(**hints)
    result = provider.fetch(request)
    return (
        IMDbCache.model_validate({**result.model_dump(), "fetched_at": int(time.time())})
        if result
        else None
    )


def _lookup_title(
    card: schemas.Card, omdb: OMDbRatingsProvider
) -> tuple[IMDbCache | None, list[IMDbCache | ProviderMapping]]:
    # shortcut: OMDb selects namesakes; use search if ambiguity needs review.
    fetched = _fetch(omdb, title=card.title, year=card.year, type=card.type)
    if fetched is None or not matches(fetched, card, card.title):
        return None, []
    mapping = ProviderMapping(
        provider=card.provider,
        provider_id=card.provider_id,
        imdb_id=fetched.imdb_id,
        lookup_title=card.title,
        lookup_year=card.year,
        lookup_type=card.type,
    )
    return fetched, [fetched, mapping]


def _lookup(
    card: schemas.Card,
    mapping: ProviderMapping | None,
    cached: IMDbCache | None,
    omdb: OMDbRatingsProvider,
) -> tuple[IMDbCache | None, list[IMDbCache | ProviderMapping]]:
    if mapping is None or (cached and not matches(cached, card, mapping.lookup_title)):
        return _lookup_title(card, omdb)
    if cached and time.time() - cached.fetched_at < CACHE_TTL:
        return cached, []
    fetched = _fetch(omdb, imdb_id=mapping.imdb_id)
    if fetched and matches(fetched, card, mapping.lookup_title):
        return fetched, [fetched]
    return _lookup_title(card, omdb)


def _with_ratings(
    row: IMDbCache | None, cached: IMDbCache | None, reeldb: ReelDBRatingsProvider
) -> IMDbCache | None:
    if (
        row is None
        or (row.rating is not None and row.votes is not None)
        or not reeldb.api_key.get_secret_value()
    ):
        return row
    # shortcut: unrated results retry per request; add a TTL if quota binds.
    if cached and cached.rating is not None and cached.votes is not None:
        return cached
    fetched = _fetch(reeldb, imdb_id=row.imdb_id)
    if fetched is None or fetched.rating is None or fetched.votes is None:
        return row
    return row.model_copy(
        update={"rating": fetched.rating, "votes": fetched.votes, "fetched_at": fetched.fetched_at}
    )


def _resolution(card: schemas.Card, row: IMDbCache | None) -> schemas.Resolution:
    rating = (
        schemas.Rating(imdb_id=row.imdb_id, rating=row.rating, votes=row.votes)
        if row and row.rating is not None and row.votes is not None
        else None
    )
    return schemas.Resolution(
        request_id=card.request_id,
        status="matched" if rating else "not_found",
        rating=rating,
    )


def resolve_card(
    card: schemas.Card,
    lookup: tuple[IMDbCache | None, list[IMDbCache | ProviderMapping]],
    cached: IMDbCache | None,
    reeldb: ReelDBRatingsProvider,
) -> tuple[schemas.Resolution, list[IMDbCache | ProviderMapping]]:
    looked_up, pending = lookup
    found_by_title = any(isinstance(record, ProviderMapping) for record in pending)
    row = (
        cached
        if looked_up
        and cached
        and found_by_title
        and time.time() - cached.fetched_at < CACHE_TTL
        and cached.year == looked_up.year
        and cached.type == looked_up.type
        else looked_up
    )
    rated = _with_ratings(row, cached, reeldb)
    writes: list[IMDbCache | ProviderMapping] = (
        [rated, *(record for record in pending if isinstance(record, ProviderMapping))]
        if rated is not None and rated is not looked_up
        else pending
    )
    return _resolution(card, rated), writes


def _map_limit(items, limit, fn, *args):
    with ThreadPoolExecutor(max_workers=limit) as pool:
        futures = [pool.submit(fn, *item, *args) for item in items]
        return [future.result() for future in futures]


def resolve(config: Settings, cards: list[schemas.Card], db: Session) -> schemas.ResolveResponse:
    inputs = cache.load(db, cards)
    with httpx.Client(timeout=2) as client:
        omdb = OMDbRatingsProvider(client, config.omdb_api_key)
        reeldb = ReelDBRatingsProvider(client, config.reeldb_api_key)
        lookups = _map_limit(inputs, 8, _lookup, omdb)
        existing = [db.get(IMDbCache, row.imdb_id) if row else None for row, _ in lookups]
        resolved = _map_limit(zip(cards, lookups, existing, strict=True), 8, resolve_card, reeldb)

    cache.save(db, [record for _, writes in resolved for record in writes])

    return schemas.ResolveResponse(
        results=[result for result, _ in resolved],
        dataset_version="omdb",
        dataset_date=datetime.now(UTC).date().isoformat(),
        matcher_version=constants.MATCHER_VERSION,
    )
