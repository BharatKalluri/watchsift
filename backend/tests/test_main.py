from httpx import ASGITransport, AsyncClient

from src.main import create_app


async def test_retired_endpoints_are_absent(client):
    for path in ("/v1/metrics", "/v1/unmatched"):
        assert (await client.post(path, json={})).status_code == 404
    for provider in ("netflix", "primevideo"):
        assert (await client.get(f"/v1/providers/{provider}/config")).status_code == 404
    schema = (await client.get("/openapi.json")).json()
    assert set(schema["paths"]) == {"/health", "/v1/resolve"}


async def test_rate_limit(config):
    config.requests_per_minute = 1
    app = create_app(config)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"cards": [{"request_id": "0", "netflix_id": "123", "title": "Unknown"}]}
        assert (await client.post("/v1/resolve", json=payload)).status_code == 200
        response = await client.post("/v1/resolve", json=payload)
        assert response.status_code == 429
        assert int(response.headers["retry-after"]) > 0


async def test_production_starts_and_serves_catalogue(config):
    config.environment = "production"
    app = create_app(config)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/health")).status_code == 200
            payload = {"cards": [{"request_id": "0", "netflix_id": "123", "title": "Unknown"}]}
            assert (await client.post("/v1/resolve", json=payload)).status_code == 200
            assert (await client.get("/openapi.json")).status_code == 404
