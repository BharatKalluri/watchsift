from pathlib import Path

from sqlalchemy.dialects.sqlite import insert
from sqlmodel import Session, select

from src.catalogue import constants, schemas, utils
from src.catalogue.models import Alias, Metadata, ProviderMapping, Title
from src.database import catalogue_connection, operations_session


def matching_rows(
    db: Session, card: schemas.Card, title: str, imdb_id: str | None = None
) -> list[Title]:
    statement = select(Title).join(Alias).where(Alias.normalized == utils.normalize_title(title))
    if imdb_id is not None:
        statement = statement.where(Title.imdb_id == imdb_id)
    if card.year is not None:
        statement = statement.where(Title.year == card.year)
    if card.type is not None:
        # Netflix includes one-off specials in both its film and show rows.
        statement = statement.where(Title.kind.in_([card.type, "special"]))
    return list(db.exec(statement.order_by(Title.votes.desc())).all())


def resolve(
    data_dir: Path, cards: list[schemas.Card], *, use_mappings: bool = True
) -> schemas.ResolveResponse:
    with catalogue_connection(data_dir) as db, operations_session(data_dir) as mappings:
        metadata = dict(db.exec(select(Metadata.key, Metadata.value)).all())
        results = []
        for card in cards:
            cached = (
                mappings.exec(
                    select(ProviderMapping.imdb_id).where(
                        ProviderMapping.provider == card.provider,
                        ProviderMapping.provider_id == card.provider_id,
                    )
                ).first()
                if use_mappings
                else None
            )
            cached_rows = []
            if cached:
                for title in [card.title, *utils.title_variants(card.title)]:
                    cached_rows = matching_rows(db, card, title, cached)
                    if cached_rows:
                        break
            rows = cached_rows or matching_rows(db, card, card.title)
            fallback = False
            if not rows:
                # Only exact, unique fallback names; never fuzzy-match a sequel or remake.
                candidates = {}
                for variant in utils.title_variants(card.title):
                    for row in matching_rows(db, card, variant):
                        candidates[row.imdb_id] = row
                rows = list(candidates.values())
                fallback = True
            else:
                primary = [
                    row
                    for row in rows
                    if utils.title_identity(row.primary_title) == utils.title_identity(card.title)
                ]
                # Keep alias competitors when a primary namesake may be an unrated new remake.
                if primary and (
                    len(primary) == 1 or all(row.rating is not None for row in primary)
                ):
                    rows = primary
            status = "not_found"
            if len(rows) > 1:
                status = "ambiguous"
                # Popularity is a heuristic; close namesakes remain unresolved.
                if not fallback and (rows[0].votes or 0) >= max(
                    1000, 100 * max(rows[1].votes or 0, 1)
                ):
                    status = "matched"
            elif rows and rows[0].rating is not None:
                status = "matched"
            rating = (
                schemas.Rating(imdb_id=rows[0].imdb_id, rating=rows[0].rating, votes=rows[0].votes)
                if status == "matched"
                else None
            )
            # Share unique year matches and dominant matches qualified by both year and type.
            if (
                use_mappings
                and rating
                and card.year is not None
                and (len(rows) == 1 or card.type is not None)
            ):
                statement = insert(ProviderMapping).values(
                    provider=card.provider, provider_id=card.provider_id, imdb_id=rating.imdb_id
                )
                mappings.execute(
                    statement.on_conflict_do_update(
                        index_elements=["provider", "provider_id"],
                        set_={"imdb_id": statement.excluded.imdb_id},
                    )
                )
            results.append(
                schemas.Resolution(request_id=card.request_id, status=status, rating=rating)
            )
    return schemas.ResolveResponse(
        results=results,
        dataset_version=metadata["version"],
        dataset_date=metadata["date"],
        matcher_version=constants.MATCHER_VERSION,
    )
