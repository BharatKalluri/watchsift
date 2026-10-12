"""Create a tiny synthetic catalogue for extension integration tests, without IMDb exports."""

import sqlite3
from pathlib import Path

from src.catalogue.importer import activate
from src.catalogue.utils import normalize_title


def seed(data_dir: Path):
    if data_dir.exists() and any(data_dir.iterdir()):
        raise FileExistsError("Use a fresh test data directory")
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "catalogue-test.sqlite3"
    if path.exists():
        raise FileExistsError("Use a fresh test data directory")
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE title (imdb_id TEXT PRIMARY KEY, primary_title TEXT,
                                year INTEGER, kind TEXT, rating REAL, votes INTEGER);
            CREATE TABLE alias (normalized TEXT, imdb_id TEXT, PRIMARY KEY(normalized, imdb_id));
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);
        """)
        for imdb_id, name, year, rating, votes in [
            ("tt0111161", "The Shawshank Redemption", 1994, 7.0, 1000),
            ("tt0052077", "Plan 9 from Outer Space", 1958, 6.9, 10000),
        ]:
            db.execute(
                "INSERT INTO title VALUES (?, ?, ?, 'movie', ?, ?)",
                (imdb_id, name, year, rating, votes),
            )
            db.execute("INSERT INTO alias VALUES (?, ?)", (normalize_title(name), imdb_id))
        db.executemany(
            "INSERT INTO metadata VALUES (?, ?)",
            [("date", "2026-10-11"), ("version", "synthetic-tests")],
        )
    activate(data_dir, path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_dir", type=Path)
    seed(parser.parse_args().data_dir)
