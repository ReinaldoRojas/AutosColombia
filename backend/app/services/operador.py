from functools import wraps

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Operador
from app.schemas.operador import OperadorActualizar, OperadorCrear


class OperadorError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


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
            if code == "23505" and constraint == "uq_operador_telefono":
                raise OperadorError(409, "Ya existe un operador con ese teléfono.") from None
            if code == "23503":
                raise OperadorError(409, "El operador tiene registros relacionados y no se puede eliminar.") from None
            if code in {"23502", "23514"}:
                raise OperadorError(422, "Los datos incumplen las restricciones del operador.") from None
            raise OperadorError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError:
            session.rollback()
            raise OperadorError(503, "No se pudo completar la operación con la base de datos.") from None
    return wrapped


def find_operator(session: Session, operator_id: int) -> Operador:
    operator = session.get(Operador, operator_id)
    if operator is None:
        raise OperadorError(404, "Operador no encontrado.")
    return operator


@database_operation
def create_operator(session: Session, data: OperadorCrear) -> Operador:
    operator = Operador(**data.model_dump())
    session.add(operator)
    session.commit()
    session.refresh(operator)
    return operator


@database_operation
def list_operators(session: Session, offset: int, limit: int) -> dict:
    total = session.scalar(select(func.count()).select_from(Operador))
    items = list(session.scalars(select(Operador).order_by(Operador.id).offset(offset).limit(limit)))
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@database_operation
def get_operator(session: Session, operator_id: int) -> Operador:
    return find_operator(session, operator_id)


@database_operation
def update_operator(session: Session, operator_id: int, data: OperadorActualizar) -> Operador:
    operator = find_operator(session, operator_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(operator, key, value)
    session.commit()
    session.refresh(operator)
    return operator


@database_operation
def delete_operator(session: Session, operator_id: int) -> None:
    operator = find_operator(session, operator_id)
    session.delete(operator)
    session.commit()


