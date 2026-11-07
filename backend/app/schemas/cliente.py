import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, field_validator

from app.models import required_text
from app.schemas.vehiculo import Texto, VehiculoRespuesta

TELEFONO = re.compile(r"3[0-9]{9}|60[1-8][0-9]{7}")
CORREO = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def normalizar_documento(value: str) -> str:
    documento = re.sub(r"[\s.\-]", "", required_text(value, "El documento")).upper()
    if not re.fullmatch(r"[0-9A-Z]{3,20}", documento):
        raise ValueError("El documento debe tener entre 3 y 20 letras o números, sin símbolos.")
    return documento


def normalizar_telefono(value: str) -> str:
    telefono = re.sub(r"[\s\-()]", "", required_text(value, "El teléfono"))
    telefono = re.sub(r"^\+?57", "", telefono) if len(telefono) > 10 else telefono
    if not TELEFONO.fullmatch(telefono):
        raise ValueError("El teléfono debe ser un celular colombiano (3001234567) o un fijo (6011234567).")
    return telefono


def normalizar_correo(value: str | None) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    correo = required_text(value, "El correo").lower()
    if not CORREO.fullmatch(correo):
        raise ValueError("El correo no tiene un formato válido (ejemplo: nombre@correo.com).")
    return correo


Documento = Annotated[str, BeforeValidator(normalizar_documento)]
Telefono = Annotated[str, BeforeValidator(normalizar_telefono)]
Correo = Annotated[str | None, BeforeValidator(normalizar_correo)]
TipoDocumento = Literal["CC", "CE", "TI", "PA", "NIT"]


class ClienteCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo_documento: TipoDocumento
    numero_documento: Documento
    nombres: Texto
    apellidos: Texto
    telefono: Telefono
    correo: Correo = None


class ClienteActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo_documento: TipoDocumento | None = None
    numero_documento: Documento | None = None
    nombres: Texto | None = None
    apellidos: Texto | None = None
    telefono: Telefono | None = None
    correo: Correo = None

    @field_validator("tipo_documento", "numero_documento", "nombres", "apellidos", "telefono", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Los campos enviados no pueden ser nulos.")
        return value


class ClienteRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo_documento: str
    numero_documento: str
    nombres: str
    apellidos: str
    telefono: str
    correo: str | None
    fecha_registro: datetime


class ClienteDetalle(ClienteRespuesta):
    vehiculos: list[VehiculoRespuesta]


class ClientesPagina(BaseModel):
    items: list[ClienteRespuesta]
    total: int
    offset: int
    limit: int
