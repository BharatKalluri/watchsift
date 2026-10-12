import pytest

from src.catalogue.schemas import Card, ResolveRequest


@pytest.mark.parametrize(
    "year,duration,row,expected",
    [
        ("2020", "2h 4m", None, (2020, "movie")),
        ("2026", "Limited Series", None, (2026, "series")),
        ("wrong", "7 Episodes", None, (None, "series")),
        ("9999", "", "Movies & TV Shows", (None, None)),
        (None, None, "Critically Acclaimed TV Shows", (None, "series")),
        (None, None, "Award-Winning Films", (None, "movie")),
    ],
)
def test_metadata_interpretation(year, duration, row, expected):
    card = Card(
        request_id="0",
        netflix_id="123",
        title="Example",
        raw_year=year,
        duration=duration,
        row_label=row,
    )
    assert (card.year, card.type) == expected


def test_type_hints_shared_only_for_consistent_provider_identity():
    def card(id, **kwargs):
        return Card(request_id=id, netflix_id="123", title="Example", **kwargs)

    payload = ResolveRequest(cards=[card("0", row_label="TV Shows"), card("1")])
    assert [c.type for c in payload.cards] == ["series", "series"]
    payload = ResolveRequest(
        cards=[card("0", row_label="TV Shows"), card("1", explicit_type="movie"), card("2")]
    )
    assert [c.type for c in payload.cards] == ["series", "movie", None]


async def test_raw_metadata_resolves_and_seeds_shared_mapping(client):
    card = {
        "request_id": "0",
        "netflix_id": "123",
        "title": "Same Name",
        "raw_year": "2020",
        "duration": "2h 4m",
    }
    response = await client.post("/v1/resolve", json={"cards": [card]})
    assert response.json()["results"][0]["rating"]["imdb_id"] == "tt1"
    del card["raw_year"]
    del card["duration"]
    assert (await client.post("/v1/resolve", json={"cards": [card]})).json()["results"][0][
        "rating"
    ]["imdb_id"] == "tt1"
    card["raw_year"] = "0" * 301
    assert (await client.post("/v1/resolve", json={"cards": [card]})).status_code == 422


def test_detail_duration_overrides_a_grid_type_hint():
    card = Card(
        request_id="0",
        netflix_id="123",
        title="Example",
        explicit_type="movie",
        duration="Limited Series",
    )
    assert card.type == "series"


@pytest.mark.parametrize("hint,expected", [("Movie", "movie"), ("TV Show", "series")])
def test_prime_entity_hints(hint, expected):
    card = Card(
        request_id="0",
        provider="primevideo",
        provider_id="B000000001",
        title="Example",
        explicit_type=hint,
    )
    assert card.type == expected


async def test_prime_mapping_is_separate_from_netflix(client):
    prime = {
        "request_id": "0",
        "provider": "primevideo",
        "provider_id": "1234567890",
        "title": "Same Name",
        "raw_year": "2020",
        "explicit_type": "Movie",
    }
    netflix = {**prime, "provider": "netflix", "raw_year": "2021"}
    assert (await client.post("/v1/resolve", json={"cards": [prime]})).json()["results"][0][
        "rating"
    ]["imdb_id"] == "tt1"
    assert (await client.post("/v1/resolve", json={"cards": [netflix]})).json()["results"][0][
        "rating"
    ]["imdb_id"] == "tt2"
    del prime["raw_year"]
    assert (await client.post("/v1/resolve", json={"cards": [prime]})).json()["results"][0][
        "rating"
    ]["imdb_id"] == "tt1"
    for bad in ["lowercase1", "123", "x" * 101]:
        assert (
            await client.post("/v1/resolve", json={"cards": [{**prime, "provider_id": bad}]})
        ).status_code == 422
