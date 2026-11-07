import re
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from app.models import required_text


Texto = Annotated[str, BeforeValidator(lambda value: required_text(value, "El campo"))]
SEPARADORES_PLACA = re.compile(r"[\s\-]")
PLACA_COLOMBIANA = re.compile(r"[A-Z]{3}[0-9]{2}[0-9A-Z]")


def normalizar_placa(value: str) -> str:
    """Devuelve la placa en mayúsculas y sin separadores: ABC123 (carro) o ABC12D (moto)."""
    placa = SEPARADORES_PLACA.sub("", required_text(value, "La placa")).upper()
    if not PLACA_COLOMBIANA.fullmatch(placa):
        raise ValueError(
            "La placa debe ser colombiana: tres letras y tres números (ABC123) "
            "o, en motos, tres letras, dos números y una letra (ABC12D)."
        )
    return placa


Placa = Annotated[str, BeforeValidator(normalizar_placa)]
Anio = Annotated[int, Field(strict=True, ge=1, le=9999)]
IdCliente = Annotated[int, Field(strict=True, ge=1, le=9223372036854775807)]
TipoVehiculo = Annotated[
    Literal["MOTO", "CARRO", "CAMIONETA"],
    BeforeValidator(lambda value: required_text(value, "tipo")),
]


class VehiculoCrear(BaseModel):
    """RF-02: todo vehículo nuevo pertenece a un cliente y trae su fecha de pago."""
    model_config = ConfigDict(extra="forbid")

    placa: Placa
    color: Texto
    modelo: Anio
    marca: Texto
    tipo: TipoVehiculo
    cliente_id: IdCliente
    linea: Texto
    fecha_pago: date


class VehiculoActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    placa: Placa | None = None
    color: Texto | None = None
    modelo: Anio | None = None
    marca: Texto | None = None
    tipo: TipoVehiculo | None = None
    cliente_id: IdCliente | None = None
    linea: Texto | None = None
    fecha_pago: date | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Los campos enviados no pueden ser nulos.")
        return value


class VehiculoRespuesta(BaseModel):
    """Los vehículos anteriores a la revisión 0005 pueden no tener cliente, línea ni pago."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    placa: str
    color: str
    modelo: int
    marca: str
    tipo: str
    cliente_id: int | None
    linea: str | None
    fecha_pago: date | None
    fecha_vencimiento: date | None


class VehiculosPagina(BaseModel):
    items: list[VehiculoRespuesta]
    total: int
    offset: int
    limit: int
