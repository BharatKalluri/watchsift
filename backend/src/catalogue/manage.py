"""Rollback the active catalogue to its previous snapshot."""

import argparse
from pathlib import Path

from sqlmodel import Session, text

from src.catalogue.importer import activate
from src.database import database_engine


def rollback(data_dir: Path) -> None:
    previous = (data_dir / "previous.sqlite3").resolve(strict=True)
    with Session(database_engine(previous, readonly=True)) as db:
        if db.execute(text("PRAGMA integrity_check")).scalar_one() != "ok":
            raise ValueError("Previous snapshot failed validation")
    activate(data_dir, previous)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["rollback"])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    rollback(args.data_dir)
