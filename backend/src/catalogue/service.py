import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial

import httpx
from sqlmodel import Session

from src.catalogue import dao, schemas, utils
from src.catalogue.constants import CACHE_TTL, MATCHER_VERSION, MAX_CONCURRENT_LOOKUPS
from src.catalogue.models import IMDbCache, ProviderMapping
from src.catalogue.ratings_providers import (
    OMDbRatingsProvider,
    RatingsProvider,
    ReelDBRatingsProvider,
)
from src.config import Settings


@dataclass
class Lookup:
    card: schemas.Card
    mapping: ProviderMapping | None
    cached: IMDbCache | None  # Last stored row for the matched title, fresh or stale.
    row: IMDbCache | None = None
    new_mapping: ProviderMapping | None = None


def resolve(config: Settings, cards: list[schemas.Card], db: Session) -> schemas.ResolveResponse:
    known = dao.get_known(db, [(card.provider, card.provider_id) for card in cards])
    lookups = [
        Lookup(card, *known.get((card.provider, card.provider_id), (None, None))) for card in cards
    ]
    with (
        httpx.Client(timeout=2) as client,
        ThreadPoolExecutor(max_workers=MAX_CONCURRENT_LOOKUPS) as pool,
    ):
        # Provider calls run in the pool; the database stays on the caller's thread.
        fetch = partial(_fetch_unique, pool)
        omdb = OMDbRatingsProvider(client, config.omdb_api_key)
        _use_cache_or_refresh(lookups, fetch, omdb)
        _search_titles(lookups, fetch, omdb)
        _attach_stored_rows(lookups, db)
        _fill_ratings(lookups, fetch, ReelDBRatingsProvider(client, config.reeldb_api_key))
    dao.save(db, _writes(lookups))
    return schemas.ResolveResponse(
        results=[_resolution(lookup) for lookup in lookups],
        dataset_version="omdb",
        dataset_date=datetime.now(UTC).date().isoformat(),
        matcher_version=MATCHER_VERSION,
    )


def _use_cache_or_refresh(lookups: list[Lookup], fetch, omdb: OMDbRatingsProvider) -> None:
    """Fresh mapped rows need no call; stale ones refresh by IMDb ID."""
    stale = []
    for lookup in lookups:
        mapping, cached = lookup.mapping, lookup.cached
        if mapping is None or (cached and not _matches(cached, lookup.card, mapping.lookup_title)):
            continue
        if _fresh(cached):
            lookup.row = cached
        else:
            stale.append(lookup)
    requests = [schemas.RatingsProviderRequest(imdb_id=lookup.mapping.imdb_id) for lookup in stale]
    for lookup, row in zip(stale, fetch(omdb, requests), strict=True):
        if row and _matches(row, lookup.card, lookup.mapping.lookup_title):
            lookup.row = row


def _search_titles(lookups: list[Lookup], fetch, omdb: OMDbRatingsProvider) -> None:
    # shortcut: OMDb selects namesakes; use search if ambiguity needs review.
    pending = [lookup for lookup in lookups if lookup.row is None]
    requests = [
        schemas.RatingsProviderRequest(title=card.title, year=card.year, type=card.type)
        for card in (lookup.card for lookup in pending)
    ]
    for lookup, row in zip(pending, fetch(omdb, requests), strict=True):
        card = lookup.card
        if row is None or not _hints_match(row, card):
            continue
        lookup.row = row
        lookup.new_mapping = ProviderMapping(
            provider=card.provider,
            provider_id=card.provider_id,
            imdb_id=row.imdb_id,
            lookup_title=card.title,
            lookup_year=card.year,
            lookup_type=card.type,
        )


def _attach_stored_rows(lookups: list[Lookup], db: Session) -> None:
    """A title search can land on a title already cached, e.g. by another provider."""
    searched = [lookup for lookup in lookups if lookup.new_mapping]
    stored = dao.get_cached(db, {lookup.row.imdb_id for lookup in searched})
    for lookup in searched:
        lookup.cached = stored.get(lookup.row.imdb_id)


def _fill_ratings(lookups: list[Lookup], fetch, reeldb: ReelDBRatingsProvider) -> None:
    """Fill ratings OMDb lacks: stored ratings first, then ReelDB once per IMDb ID."""
    pending = []
    for lookup in lookups:
        row, cached = lookup.row, lookup.cached
        if row is None or row is cached or _rated(row):
            continue  # Cache hits already had their one ReelDB attempt.
        if cached and cached.imdb_id == row.imdb_id and _rated(cached):
            lookup.row = _with_ratings(row, cached)
        elif reeldb.configured:
            pending.append(lookup)
    requests = [schemas.RatingsProviderRequest(imdb_id=lookup.row.imdb_id) for lookup in pending]
    for lookup, rated in zip(pending, fetch(reeldb, requests), strict=True):
        if rated and _rated(rated):
            lookup.row = _with_ratings(lookup.row, rated)


def _writes(lookups: list[Lookup]) -> list[IMDbCache | ProviderMapping]:
    rows = {
        lookup.row.imdb_id: lookup.row
        for lookup in lookups
        if lookup.row and lookup.row is not lookup.cached
    }
    return [*rows.values(), *(lookup.new_mapping for lookup in lookups if lookup.new_mapping)]


def _resolution(lookup: Lookup) -> schemas.Resolution:
    row, request_id = lookup.row, lookup.card.request_id
    if row is None or not _rated(row):
        return schemas.Resolution(request_id=request_id, status="not_found")
    rating = schemas.Rating(imdb_id=row.imdb_id, rating=row.rating, votes=row.votes)
    return schemas.Resolution(request_id=request_id, status="matched", rating=rating)


def _fetch_unique(
    pool: ThreadPoolExecutor,
    provider: RatingsProvider,
    requests: list[schemas.RatingsProviderRequest],
) -> list[IMDbCache | None]:
    """Call the provider once per distinct request, returning results in request order."""
    unique = list(dict.fromkeys(requests))
    results = dict(zip(unique, pool.map(partial(_fetch, provider), unique), strict=True))
    return [results[request] for request in requests]


def _fetch(provider: RatingsProvider, request: schemas.RatingsProviderRequest) -> IMDbCache | None:
    result = provider.fetch(request)
    if result is None:
        return None
    return IMDbCache.model_validate({**result.model_dump(), "fetched_at": int(time.time())})


def _with_ratings(row: IMDbCache, source: IMDbCache) -> IMDbCache:
    return row.model_copy(update={"rating": source.rating, "votes": source.votes})


def _matches(row: IMDbCache, card: schemas.Card, alias: str | None) -> bool:
    titles = {utils.title_identity(row.title), utils.title_identity(alias or row.title)}
    return utils.title_identity(card.title) in titles and _hints_match(row, card)


def _hints_match(row: IMDbCache, card: schemas.Card) -> bool:
    return card.year in (None, row.year) and card.type in (None, row.type)


def _fresh(row: IMDbCache | None) -> bool:
    return row is not None and time.time() - row.fetched_at < CACHE_TTL


def _rated(row: IMDbCache) -> bool:
    return row.rating is not None and row.votes is not None
