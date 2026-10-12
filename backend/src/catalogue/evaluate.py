"""Evaluate human-verified Netflix mappings from CSV; never infer the expected IMDb IDs."""

import argparse
import csv
import json
from pathlib import Path

from src.catalogue.schemas import Card
from src.catalogue.service import resolve
from src.config import Settings


def evaluate(path: Path, config: Settings) -> dict:
    with path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    correct = displayed = recognized = 0
    errors = []
    for index, row in enumerate(rows):
        expected = row["expected_imdb_id"].strip()
        card = Card(
            request_id=str(index),
            netflix_id=row["netflix_id"],
            title=row["title"],
            year=int(row["year"]) if row["year"] else None,
            type=row["type"] or None,
        )
        result = resolve(config, [card], use_mappings=False).results[0]
        recognized += bool(expected)
        if result.rating:
            displayed += 1
            correct += result.rating.imdb_id == expected
            if result.rating.imdb_id != expected:
                errors.append(
                    {"title": card.title, "expected": expected, "actual": result.rating.imdb_id}
                )
    precision = correct / displayed if displayed else None
    coverage = correct / recognized if recognized else 0
    return {
        "titles": len(rows),
        "recognized": recognized,
        "badges": displayed,
        "precision": precision,
        "coverage": coverage,
        "errors": errors,
        "accepted": len(rows) >= 100 and not errors and coverage >= 0.8,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    args = parser.parse_args()
    report = evaluate(args.csv, Settings())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["accepted"] else 1)
