# FastAPI structure

Always follow https://github.com/zhanymkanov/fastapi-best-practices for this backend's project structure, as requested by the user. Organize by domain under src/, with domain router.py, schemas.py, and service.py. Shared config, database connections, dependencies, and main.py live directly under src/. Add other domain files only when they have an actual responsibility.

Use synchronous routes for SQLModel sessions and SQLite operations. Keep blocking work outside async routes. Test through httpx ASGITransport against real temporary SQLite databases.
