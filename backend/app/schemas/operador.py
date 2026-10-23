import re
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, field_validator

from app.models import required_text

Texto = Annotated[str, BeforeValidator(lambda value: required_text(value, "El campo"))]

SEPARADORES_TELEFONO = re.compile(r"[\s\-.()]")
TELEFONO_COLOMBIANO = re.compile(r"3[0-9]{9}|60[1-8][0-9]{7}")


def normalizar_telefono(value: str) -> str:
    """Devuelve 10 dígitos: celular (3XX) o fijo con indicativo (60X); admite prefijo +57."""
    digits = SEPARADORES_TELEFONO.sub("", required_text(value, "El teléfono"))
    for prefix in ("+57", "0057"):
        if digits.startswith(prefix):
            digits = digits[len(prefix):]
            break
    else:
        if len(digits) == 12 and digits.startswith("57"):
            digits = digits[2:]
    if not TELEFONO_COLOMBIANO.fullmatch(digits):
        raise ValueError(
            "El teléfono debe ser colombiano: celular de 10 dígitos que empieza por 3 "
            "o fijo con indicativo (60X), con prefijo +57 opcional."
        )
    return digits


Telefono = Annotated[str, BeforeValidator(normalizar_telefono)]


class OperadorCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Texto
    telefono: Telefono


class OperadorActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Texto | None = None
    telefono: Telefono | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Los campos enviados no pueden ser nulos.")
        return value


class OperadorRespuesta(OperadorCrear):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int


class OperadoresPagina(BaseModel):
    items: list[OperadorRespuesta]
    total: int
    offset: int
    limit: int
