from fastapi import APIRouter, HTTPException
from httpx import HTTPError
from sqlalchemy.exc import SQLAlchemyError

from src.catalogue import schemas, service
from src.dependencies import SettingsDep

router = APIRouter(prefix="/v1", tags=["catalogue"])


@router.post("/resolve", summary="Resolve visible streaming-site cards to IMDb ratings via OMDb")
def resolve(payload: schemas.ResolveRequest, config: SettingsDep) -> schemas.ResolveResponse:
    try:
        return service.resolve(config, payload.cards)
    except (HTTPError, SQLAlchemyError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, "Ratings unavailable", headers={"Retry-After": "30"}) from exc
