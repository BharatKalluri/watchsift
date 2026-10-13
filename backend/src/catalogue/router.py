import logging
import traceback

from fastapi import APIRouter, HTTPException
from httpx import HTTPError
from sqlalchemy.exc import SQLAlchemyError

from src.catalogue import schemas, service
from src.database import operations_session
from src.dependencies import SettingsDep

router = APIRouter(prefix="/v1", tags=["catalogue"])
logger = logging.getLogger("uvicorn.error")


@router.post("/resolve", summary="Resolve visible streaming-site cards to IMDb ratings via OMDb")
def resolve(payload: schemas.ResolveRequest, config: SettingsDep) -> schemas.ResolveResponse:
    try:
        with operations_session(config.database_url.get_secret_value()) as db:
            return service.resolve(config, payload.cards, db)
    except (HTTPError, SQLAlchemyError, ValueError, KeyError, TypeError) as exc:
        # Exception messages can contain API keys, query URLs, or raw input values.
        logger.error(
            "Resolve failed: cards=%d error=%s\n%s",
            len(payload.cards),
            type(exc).__name__,
            "\n".join(
                f"  {frame.filename}:{frame.lineno} in {frame.name}"
                for frame in traceback.extract_tb(exc.__traceback__)
            ),
        )
        raise HTTPException(503, "Ratings unavailable", headers={"Retry-After": "30"}) from exc
