import logging
import time
import traceback
from collections import OrderedDict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from src.catalogue import router as catalogue_router
from src.config import Settings, settings
from src.database import init_operations

logger = logging.getLogger("uvicorn.error")


def create_app(config: Settings = settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await run_in_threadpool(init_operations, config.database_url.get_secret_value())

        yield

    app = FastAPI(
        title="WatchSift API",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url="/openapi.json" if config.environment == "local" else None,
    )
    app.state.settings = config
    # shortcut: one process, replace with a shared limiter before adding replicas.
    limits: OrderedDict[str, tuple[float, int]] = OrderedDict()

    @app.middleware("http")
    async def bounded_requests(request: Request, call_next):
        if request.url.path.startswith("/v1/"):
            host = request.client.host if request.client else "unknown"
            now = time.monotonic()
            start, count = limits.pop(host, (now, 0))
            if now - start >= 60:
                start, count = now, 0
            limits[host] = (start, count + 1)
            if len(limits) > 10000:
                limits.popitem(last=False)
            if count >= config.requests_per_minute:
                return JSONResponse(
                    {"detail": "Too many requests"},
                    429,
                    headers={"Retry-After": str(max(1, int(60 - (now - start))))},
                )
            size = 0
            chunks = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 65536:
                    return JSONResponse({"detail": "Request too large"}, 413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Never echo Netflix metadata back into error logs or diagnostics.
        return JSONResponse({"detail": "Invalid request fields"}, 422)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.error(
            "Storage unavailable: path=%s error=%s\n%s",
            request.url.path,
            type(exc).__name__,
            "\n".join(
                f"  {frame.filename}:{frame.lineno} in {frame.name}"
                for frame in traceback.extract_tb(exc.__traceback__)
            ),
        )
        return JSONResponse({"detail": "Storage unavailable"}, 503, headers={"Retry-After": "30"})

    @app.get("/health", tags=["health"])
    def health():
        if not config.omdb_api_key.get_secret_value():
            return JSONResponse({"status": "omdb_key_missing"}, 503)
        return {"status": "ok", "dataset_version": "omdb"}

    app.include_router(catalogue_router.router)
    return app


app = create_app()
