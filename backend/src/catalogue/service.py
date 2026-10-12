import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from functools import lru_cache
from threading import Lock

import httpx

from src.catalogue import constants, schemas, utils
from src.catalogue.models import IMDbCache, ProviderMapping
from src.catalogue.ratings_providers import OMDbRatingsProvider, ReelDBRatingsProvider
from src.config import Settings
from src.database import operations_session

CACHE_TTL = 7 * 24 * 60 * 60
# shortcut: locks coordinate one process; use shared coordination before adding replicas.
MAPPING_LOCKS = [Lock() for _ in range(256)]
CACHE_LOCKS = [Lock() for _ in range(256)]


def matches(row: IMDbCache, card: schemas.Card, lookup_title: str | None = None) -> bool:
    return (
        utils.title_identity(card.title)
        in {utils.title_identity(row.title), utils.title_identity(lookup_title or row.title)}
        and (card.year is None or card.year == row.year)
        and (card.type is None or card.type == row.type)
    )


def resolve(
    config: Settings, cards: list[schemas.Card], *, use_mappings: bool = True
) -> schemas.ResolveResponse:
    groups = defaultdict(list)
    for index, card in enumerate(cards):
        groups[card.provider, card.provider_id].append((index, card))
    storage = config.database_url.get_secret_value()

    with httpx.Client(timeout=2) as client:
        omdb = OMDbRatingsProvider(client, config.omdb_api_key)
        reeldb = ReelDBRatingsProvider(client, config.reeldb_api_key)

        @lru_cache(maxsize=200)
        def fetch(title=None, year=None, kind=None, imdb_id=None):
            result = omdb.fetch(
                schemas.RatingsProviderRequest(title=title, year=year, type=kind, imdb_id=imdb_id)
            )
            return (
                IMDbCache.model_validate({**result.model_dump(), "fetched_at": int(time.time())})
                if result
                else None
            )

        @lru_cache(maxsize=200)
        def fallback(imdb_id):
            return reeldb.fetch(schemas.RatingsProviderRequest(imdb_id=imdb_id))

        def by_id(imdb_id):
            with CACHE_LOCKS[hash((storage, imdb_id)) % len(CACHE_LOCKS)]:
                with operations_session(storage) as db:
                    row = db.get(IMDbCache, imdb_id)
                if row and time.time() - row.fetched_at < CACHE_TTL:
                    return row
                row = fetch(imdb_id=imdb_id)
                if row:
                    with operations_session(storage) as db:
                        db.merge(row)
                return row

        def resolve_group(group):
            identity, entries = group
            results = []
            with MAPPING_LOCKS[hash((storage, identity)) % len(MAPPING_LOCKS)]:
                for index, card in entries:
                    row = None
                    mapping = None
                    if use_mappings:
                        with operations_session(storage) as db:
                            mapping = db.get(ProviderMapping, identity)
                            cached = db.get(IMDbCache, mapping.imdb_id) if mapping else None
                        if mapping and (
                            cached is None or matches(cached, card, mapping.lookup_title)
                        ):
                            row = by_id(mapping.imdb_id)
                            if row and not matches(row, card, mapping.lookup_title):
                                row = None
                    if row is None:
                        # shortcut: OMDb selects namesakes; use search if ambiguity needs review.
                        row = fetch(card.title, card.year, card.type)
                        if row and (
                            (card.year is not None and card.year != row.year)
                            or (card.type is not None and card.type != row.type)
                        ):
                            row = None
                        if row and use_mappings:
                            with CACHE_LOCKS[hash((storage, row.imdb_id)) % len(CACHE_LOCKS)]:
                                with operations_session(storage) as db:
                                    cached = db.get(IMDbCache, row.imdb_id)
                                    if (
                                        cached
                                        and time.time() - cached.fetched_at < CACHE_TTL
                                        and cached.year == row.year
                                        and cached.type == row.type
                                    ):
                                        row = cached
                                    else:
                                        db.merge(row)
                                    db.merge(
                                        ProviderMapping(
                                            provider=card.provider,
                                            provider_id=card.provider_id,
                                            imdb_id=row.imdb_id,
                                            lookup_title=card.title,
                                            lookup_year=card.year,
                                            lookup_type=card.type,
                                        )
                                    )
                    if (
                        row
                        and (row.rating is None or row.votes is None)
                        and config.reeldb_api_key.get_secret_value()
                    ):
                        # shortcut: unrated results retry per request; add a TTL if quota binds.
                        with CACHE_LOCKS[hash((storage, row.imdb_id)) % len(CACHE_LOCKS)]:
                            if use_mappings:
                                with operations_session(storage) as db:
                                    cached = db.get(IMDbCache, row.imdb_id)
                                if (
                                    cached
                                    and cached.rating is not None
                                    and cached.votes is not None
                                ):
                                    row.rating, row.votes = cached.rating, cached.votes
                            if row.rating is None or row.votes is None:
                                result = fallback(row.imdb_id)
                                if (
                                    result
                                    and result.rating is not None
                                    and result.votes is not None
                                ):
                                    row.rating, row.votes = result.rating, result.votes
                                    row.fetched_at = int(time.time())
                                    if use_mappings:
                                        with operations_session(storage) as db:
                                            db.merge(row)
                    rating = (
                        schemas.Rating(imdb_id=row.imdb_id, rating=row.rating, votes=row.votes)
                        if row and row.rating is not None and row.votes is not None
                        else None
                    )
                    results.append(
                        (
                            index,
                            schemas.Resolution(
                                request_id=card.request_id,
                                status="matched" if rating else "not_found",
                                rating=rating,
                            ),
                        )
                    )
            return results

        # Cards sharing a provider ID keep their original order.
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = [
                entry for group in pool.map(resolve_group, groups.items()) for entry in group
            ]

    return schemas.ResolveResponse(
        results=[result for _, result in sorted(results, key=lambda entry: entry[0])],
        dataset_version="omdb",
        dataset_date=datetime.now(UTC).date().isoformat(),
        matcher_version=constants.MATCHER_VERSION,
    )
