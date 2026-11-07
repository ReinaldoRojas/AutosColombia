from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Puerta
from app.schemas.estancia import PuertaRespuesta
from app.services.estancia import EstanciaError

router = APIRouter(prefix="/puertas", tags=["Puertas"])
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.get("", response_model=list[PuertaRespuesta])
def list_all(session: DatabaseSession):
    try:
        return list(session.scalars(select(Puerta).order_by(Puerta.id)))
    except SQLAlchemyError:
        raise EstanciaError(503, "No se pudo completar la operación con la base de datos.") from None
