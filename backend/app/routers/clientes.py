from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas.cliente import ClienteActualizar, ClienteCrear, ClienteDetalle, ClientesPagina
from app.services import cliente as service

router = APIRouter(prefix="/clientes", tags=["Clientes"])
DatabaseSession = Annotated[Session, Depends(get_session)]
ClientId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.post("", response_model=ClienteDetalle, status_code=201)
def create(data: ClienteCrear, session: DatabaseSession):
    return service.create_client(session, data)


@router.get("", response_model=ClientesPagina)
def list_all(
    session: DatabaseSession,
    q: Annotated[str | None, Query(max_length=100, description="Documento, nombres o apellidos")] = None,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return service.list_clients(session, q, offset, limit)


@router.get("/{id}", response_model=ClienteDetalle)
def get_one(id: ClientId, session: DatabaseSession):
    return service.get_client(session, id)


@router.patch("/{id}", response_model=ClienteDetalle)
def update(id: ClientId, data: ClienteActualizar, session: DatabaseSession):
    return service.update_client(session, id, data)
