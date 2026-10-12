from src.catalogue.schemas import Card


def card(title, **kwargs):
    return Card(request_id="0", netflix_id="123", title=title, **kwargs)


async def test_resolve_and_validation(client):
    response = await client.post(
        "/v1/resolve", json={"cards": [card("Alternate Title").model_dump()]}
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["rating"] == {
        "imdb_id": "tt1",
        "rating": 7.0,
        "votes": 1000,
    }
    response = await client.post(
        "/v1/resolve", json={"cards": [card("Alternate Title").model_dump()] * 51}
    )
    assert response.status_code == 422
    assert "Alternate Title" not in response.text
    assert (await client.get("/health")).status_code == 200


async def test_oversize_request(client):
    response = await client.post("/v1/resolve", content=b" " * 65537)
    assert response.status_code == 413


async def test_generic_provider_identity_and_conflicts(client):
    payload = {
        "request_id": "0",
        "provider": "other",
        "provider_id": "film:123",
        "title": "Same Name",
        "year": 2020,
        "type": "movie",
    }
    response = await client.post("/v1/resolve", json={"cards": [payload]})
    assert response.status_code == 200
    payload.pop("year")
    payload.pop("type")
    assert (await client.post("/v1/resolve", json={"cards": [payload]})).json()["results"][0][
        "rating"
    ]["imdb_id"] == "tt1"
    payload["netflix_id"] = "123"
    assert (await client.post("/v1/resolve", json={"cards": [payload]})).status_code == 422
    payload.pop("netflix_id")
    payload["provider"] = "netflix"
    assert (await client.post("/v1/resolve", json={"cards": [payload]})).status_code == 422
