from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from src.catalogue import schemas, service
from src.dependencies import SettingsDep

router = APIRouter(prefix="/v1", tags=["catalogue"])


@router.post("/resolve", summary="Resolve visible streaming-site cards to unambiguous IMDb ratings")
def resolve(payload: schemas.ResolveRequest, config: SettingsDep) -> schemas.ResolveResponse:
    try:
        return service.resolve(config.data_dir, payload.cards)
    except (FileNotFoundError, SQLAlchemyError, KeyError) as exc:
        raise HTTPException(503, "Catalogue unavailable", headers={"Retry-After": "30"}) from exc
