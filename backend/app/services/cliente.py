"""Clientes (RF-01). Los clientes no se eliminan: conservan el historial de sus vehículos (RNF-07)."""

from functools import wraps

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models import Cliente
from app.schemas.cliente import ClienteActualizar, ClienteCrear


class ClienteError(Exception):
    def __init__(self, status_code: int, detail: str, cliente_id: int | None = None) -> None:
        self.status_code = status_code
        self.detail = detail
        self.cliente_id = cliente_id


def database_operation(operation):
    """Centraliza rollback y mensajes públicos sin detalles del driver."""
    @wraps(operation)
    def wrapped(session: Session, *args, **kwargs):
        try:
            return operation(session, *args, **kwargs)
        except IntegrityError as error:
            session.rollback()
            code = getattr(error.orig, "sqlstate", None)
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if code == "23505" and constraint == "uq_cliente_documento":
                raise ClienteError(409, "El cliente ya está registrado.") from None
            if code in {"23502", "23514"}:
                raise ClienteError(422, "Los datos incumplen las restricciones del cliente.") from None
            raise ClienteError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError:
            session.rollback()
            raise ClienteError(503, "No se pudo completar la operación con la base de datos.") from None
    return wrapped


def find_client(session: Session, client_id: int) -> Cliente:
    client = session.scalar(
        select(Cliente).options(selectinload(Cliente.vehiculos)).where(Cliente.id == client_id)
    )
    if client is None:
        raise ClienteError(404, "Cliente no encontrado.")
    return client


@database_operation
def create_client(session: Session, data: ClienteCrear) -> Cliente:
    existing = session.scalar(select(Cliente.id).where(Cliente.numero_documento == data.numero_documento))
    if existing is not None:
        # HU-01 criterio 2: se informa y se devuelve el id para abrir su información.
        raise ClienteError(409, "El cliente ya está registrado.", existing)
    client = Cliente(**data.model_dump())
    session.add(client)
    session.commit()
    return find_client(session, client.id)


@database_operation
def list_clients(session: Session, search: str | None, offset: int, limit: int) -> dict:
    query = select(Cliente)
    if search:
        pattern = f"%{search.strip()}%"
        full_name = Cliente.nombres + " " + Cliente.apellidos
        query = query.where(or_(Cliente.numero_documento.ilike(pattern), full_name.ilike(pattern)))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    items = list(session.scalars(query.order_by(Cliente.apellidos, Cliente.nombres, Cliente.id)
                                 .offset(offset).limit(limit)))
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@database_operation
def get_client(session: Session, client_id: int) -> Cliente:
    return find_client(session, client_id)


@database_operation
def update_client(session: Session, client_id: int, data: ClienteActualizar) -> Cliente:
    client = find_client(session, client_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(client, key, value)
    session.commit()
    return find_client(session, client_id)
