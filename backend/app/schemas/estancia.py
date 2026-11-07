import re
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from app.models import required_text
from app.schemas.celda import CeldaRespuesta
from app.schemas.cliente import ClienteRespuesta
from app.schemas.vehiculo import Placa, VehiculoRespuesta
from app.services.mensualidad import Mensualidad

Identificador = Annotated[int, Field(strict=True, ge=1, le=9223372036854775807)]
IdPuerta = Annotated[int, Field(strict=True, ge=1, le=32767)]


def normalizar_recibo(value: str) -> str:
    """Acepta E-000245, e000245 o 245 y devuelve E-000245."""
    texto = re.sub(r"\s", "", required_text(value, "El recibo")).upper()
    match = re.fullmatch(r"(?:E-?)?0*([0-9]{1,18})", texto)
    if match is None or int(match.group(1)) == 0:
        raise ValueError("El número de recibo debe tener la forma E-000245.")
    return "E-" + match.group(1).zfill(6)


Recibo = Annotated[str, BeforeValidator(normalizar_recibo)]


def utc(value: datetime | None) -> datetime | None:
    return value.astimezone(timezone.utc) if value is not None else None


class EntradaCrear(BaseModel):
    """RF-05: la celda la asigna el sistema; el operario solo confirma."""
    model_config = ConfigDict(extra="forbid")
    placa: Placa
    operador_id: Identificador
    puerta_id: IdPuerta


class SalidaCrear(BaseModel):
    """Salida por placa, sin cambios de contrato (la búsqueda por recibo y la puerta son de RF-07)."""
    model_config = ConfigDict(extra="forbid")
    placa: Placa
    operador_id: Identificador


class PuertaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str


class OperadorResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str


class MovimientoRespuesta(BaseModel):
    """Estancia con los datos que necesita el recibo de ingreso (RF-05)."""
    id: int
    numero_recibo: str
    vehiculo_id: int
    placa: str
    tipo_vehiculo: str
    marca: str
    linea: str | None
    color: str
    cliente: str | None
    celda: CeldaRespuesta
    entrada: datetime
    salida: datetime | None
    abierta: bool
    puerta_entrada: PuertaRespuesta
    puerta_salida: PuertaRespuesta | None
    operador_entrada: OperadorResumen
    operador_salida: OperadorResumen | None

    _utc = field_validator("entrada", "salida")(utc)


class Cupo(BaseModel):
    tipo_celda: Literal["CARRO_CAMIONETA", "MOTO"]
    nombre: str
    total: int
    ocupadas: int
    disponibles: int


class ConsultaVehiculo(BaseModel):
    """RF-03 y RF-04: lo que el operario verifica antes de confirmar el ingreso."""
    vehiculo: VehiculoRespuesta
    cliente: ClienteRespuesta | None
    mensualidad: Mensualidad
    esta_dentro: bool
    estancia: MovimientoRespuesta | None
    cupo: Cupo
    puede_ingresar: bool
    motivo: str | None
