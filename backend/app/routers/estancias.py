from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas.estancia import ConsultaVehiculo, EntradaCrear, MovimientoRespuesta, Recibo, SalidaCrear
from app.schemas.vehiculo import Placa
from app.services.estancia import ServicioEstancia

router = APIRouter(prefix="/estancias", tags=["Estancias"])
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.post("/entrada", response_model=MovimientoRespuesta, status_code=201,
             summary="Registrar entrada con asignación automática de celda y recibo (RF-05)")
def entrada(data: EntradaCrear, session: DatabaseSession) -> MovimientoRespuesta:
    return ServicioEstancia(session).entrada(data)


@router.post("/salida", response_model=MovimientoRespuesta, summary="Registrar salida por placa")
def salida(data: SalidaCrear, session: DatabaseSession) -> MovimientoRespuesta:
    return ServicioEstancia(session).salida(data)


@router.get("/vehiculo/{placa}", response_model=ConsultaVehiculo,
            summary="Consultar vehículo y validar mensualidad (RF-03, RF-04)")
def consultar(placa: Placa, session: DatabaseSession) -> ConsultaVehiculo:
    return ServicioEstancia(session).consultar(placa)


@router.get("/recibo/{numero_recibo}", response_model=MovimientoRespuesta, summary="Recibo de ingreso (RF-05)")
def recibo(numero_recibo: Recibo, session: DatabaseSession) -> MovimientoRespuesta:
    return ServicioEstancia(session).recibo(numero_recibo)
