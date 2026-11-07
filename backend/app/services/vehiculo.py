from functools import wraps

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Vehiculo
from app.schemas.vehiculo import VehiculoActualizar, VehiculoCrear


class VehiculoError(Exception):
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
            if code == "23505" and constraint == "uq_vehiculo_placa":
                raise VehiculoError(409, "Ya existe un vehículo con esa placa.") from None
            if code == "23503" and constraint == "fk_vehiculo_cliente":
                raise VehiculoError(404, "Cliente no encontrado.") from None
            if code == "23503":
                raise VehiculoError(409, "El vehículo tiene registros relacionados y no se puede eliminar.") from None
            if code in {"23502", "23514"}:
                raise VehiculoError(422, "Los datos incumplen las restricciones del vehículo.") from None
            raise VehiculoError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError:
            session.rollback()
            raise VehiculoError(503, "No se pudo completar la operación con la base de datos.") from None
    return wrapped


def find_vehicle(session: Session, vehicle_id: int) -> Vehiculo:
    vehicle = session.get(Vehiculo, vehicle_id)
    if vehicle is None:
        raise VehiculoError(404, "Vehículo no encontrado.")
    return vehicle


@database_operation
def create_vehicle(session: Session, data: VehiculoCrear) -> Vehiculo:
    vehicle = Vehiculo(**data.model_dump())
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    return vehicle


@database_operation
def list_vehicles(session: Session, offset: int, limit: int) -> dict:
    total = session.scalar(select(func.count()).select_from(Vehiculo))
    items = list(session.scalars(select(Vehiculo).order_by(Vehiculo.id).offset(offset).limit(limit)))
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@database_operation
def get_vehicle(session: Session, vehicle_id: int) -> Vehiculo:
    return find_vehicle(session, vehicle_id)


@database_operation
def update_vehicle(session: Session, vehicle_id: int, data: VehiculoActualizar) -> Vehiculo:
    vehicle = find_vehicle(session, vehicle_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(vehicle, key, value)
    session.commit()
    session.refresh(vehicle)
    return vehicle


@database_operation
def delete_vehicle(session: Session, vehicle_id: int) -> None:
    vehicle = find_vehicle(session, vehicle_id)
    session.delete(vehicle)
    session.commit()
