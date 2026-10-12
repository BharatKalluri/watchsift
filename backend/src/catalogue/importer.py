"""Stream IMDb TSVs into a validated immutable catalogue snapshot."""

import argparse
import csv
import gzip
import os
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy.dialects.sqlite import insert
from sqlmodel import Session, SQLModel, func, select, text

from src.catalogue.constants import TITLE_TYPES
from src.catalogue.models import Alias, Metadata, Title
from src.catalogue.utils import normalize_title
from src.database import CATALOGUE_TABLES, database_engine


def rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as source:
        yield from csv.DictReader(source, delimiter="\t", quoting=csv.QUOTE_NONE)


def activate(data_dir: Path, snapshot: Path) -> None:
    current = data_dir / "current.sqlite3"
    if current.exists():
        previous = data_dir / "previous.next"
        previous.unlink(missing_ok=True)
        previous.symlink_to(current.resolve().name)
        os.replace(previous, data_dir / "previous.sqlite3")
    pending = data_dir / "current.next"
    pending.unlink(missing_ok=True)
    pending.symlink_to(snapshot.name)
    os.replace(pending, current)


def import_catalogue(source: Path, data_dir: Path, dataset_date: str) -> Path:
    date.fromisoformat(dataset_date)
    data_dir.mkdir(parents=True, exist_ok=True)
    version = f"{dataset_date}-{uuid.uuid4().hex[:12]}"
    destination = data_dir / f"catalogue-{version}.sqlite3"
    pending = destination.with_suffix(".building")
    try:
        engine = database_engine(pending.resolve())
        with engine.connect() as connection:
            connection.execute(text("PRAGMA journal_mode=OFF"))
            connection.execute(text("PRAGMA synchronous=OFF"))
            SQLModel.metadata.create_all(connection, tables=CATALOGUE_TABLES)
            connection.commit()
            with Session(bind=connection) as db:
                ratings = {
                    row["tconst"]: (float(row["averageRating"]), int(row["numVotes"]))
                    for row in rows(source / "title.ratings.tsv.gz")
                }
                included = set()
                aliases = []
                titles = []

                def flush():
                    if titles:
                        db.execute(insert(Title.__table__), titles)
                    if aliases:
                        db.execute(insert(Alias.__table__).on_conflict_do_nothing(), aliases)
                    db.commit()
                    titles.clear()
                    aliases.clear()

                for row in rows(source / "title.basics.tsv.gz"):
                    imdb_id = row["tconst"]
                    if row["titleType"] not in TITLE_TYPES:
                        continue
                    # Unrated names prevent a rated namesake from looking unique.
                    rating, votes = ratings.get(imdb_id, (None, None))
                    year = None if row["startYear"] == r"\N" else int(row["startYear"])
                    kind = (
                        "special"
                        if row["titleType"] == "tvSpecial"
                        else "series"
                        if row["titleType"] in {"tvSeries", "tvMiniSeries"}
                        else "movie"
                    )
                    titles.append(
                        dict(
                            imdb_id=imdb_id,
                            primary_title=row["primaryTitle"],
                            year=year,
                            kind=kind,
                            rating=rating,
                            votes=votes,
                        )
                    )
                    included.add(imdb_id)
                    for title in (row["primaryTitle"], row["originalTitle"]):
                        if title != r"\N" and (normalized := normalize_title(title)):
                            aliases.append(dict(normalized=normalized, imdb_id=imdb_id))
                    if len(titles) >= 10000:
                        flush()
                flush()
                del ratings
                rated_count = db.exec(
                    select(func.count()).select_from(Title).where(Title.rating.is_not(None))
                ).one()
                print(
                    f"Imported {len(included):,} titles ({rated_count:,} rated); scanning aliases",
                    flush=True,
                )
                for row in rows(source / "title.akas.tsv.gz"):
                    if row["titleId"] in included and row["title"] != r"\N":
                        if normalized := normalize_title(row["title"]):
                            aliases.append(dict(normalized=normalized, imdb_id=row["titleId"]))
                    if len(aliases) >= 20000:
                        flush()
                flush()
                db.add_all(
                    [
                        Metadata(key="date", value=dataset_date),
                        Metadata(key="version", value=version),
                    ]
                )
                db.commit()
                if (
                    not included
                    or not rated_count
                    or db.execute(text("PRAGMA integrity_check")).scalar_one() != "ok"
                ):
                    raise ValueError("Catalogue is empty or failed integrity validation")
                if db.execute(text("PRAGMA foreign_key_check")).first() is not None:
                    raise ValueError("Catalogue contains invalid title references")
                db.execute(text("ANALYZE"))
                db.commit()
        os.replace(pending, destination)
        activate(data_dir, destination)
        return destination
    except BaseException:
        pending.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--date", required=True, help="Dataset date, YYYY-MM-DD")
    args = parser.parse_args()
    print(import_catalogue(args.source, args.data_dir, args.date))
