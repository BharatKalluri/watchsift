import csv
import gzip

import pytest
from httpx import ASGITransport, AsyncClient

from src.catalogue.importer import import_catalogue
from src.config import Settings
from src.database import init_operations
from src.main import create_app


@pytest.fixture
def source(tmp_path):
    folder = tmp_path / "source"
    folder.mkdir()
    data = {
        "title.ratings": [
            ["tconst", "averageRating", "numVotes"],
            ["tt1", "7.0", "1000"],
            ["tt2", "8.0", "999"],
            ["tt3", "8.5", "5000"],
            ["tt4", "9.0", "10000"],
            ["tt5", "8.0", "100"],
            ["tt7", "7.8", "531"],
        ],
        "title.basics": [
            ["tconst", "titleType", "primaryTitle", "originalTitle", "startYear"],
            ["tt1", "movie", "Same Name", "Same Name", "2020"],
            ["tt2", "movie", "Same Name", "Same Name", "2021"],
            ["tt3", "tvSeries", "Same Name", "Same Name", "2020"],
            ["tt4", "tvEpisode", "Episode", "Episode", "2020"],
            ["tt5", "movie", "കുമ്പളങ്ങി നൈറ്റ്സ്", "കുമ്പളങ്ങി നൈറ്റ്സ്", r"\N"],
            ["tt6", "movie", "Unrated", "Unrated", "2022"],
            ["tt7", "tvSpecial", "Zakir Khan: Papa Yaar", "Zakir Khan: Papa Yaar", "2026"],
        ],
        "title.akas": [
            ["titleId", "title"],
            ["tt1", "Only Rated Alias"],
            ["tt6", "Only Rated Alias"],
            ["tt1", "Alternate Title"],
            ["tt1", "Alternate Title"],
            ["tt5", "Kumbalangi Nights"],
            ["tt7", "Papa Yaar by Zakir Khan"],
        ],
    }
    for name, rows in data.items():
        with gzip.open(folder / f"{name}.tsv.gz", "wt", encoding="utf-8", newline="") as stream:
            csv.writer(stream, delimiter="\t", quoting=csv.QUOTE_NONE).writerows(rows)
    return folder


@pytest.fixture
def config(tmp_path, source):
    config = Settings(data_dir=tmp_path / "data", requests_per_minute=1000)
    import_catalogue(source, config.data_dir, "2026-10-11")
    init_operations(config.data_dir)
    return config


@pytest.fixture
async def client(config):
    app = create_app(config)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
