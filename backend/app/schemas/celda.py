from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, field_validator

from app.models import required_text

Texto = Annotated[str, BeforeValidator(lambda value: required_text(value, "El campo"))]
Codigo = Annotated[Texto, AfterValidator(str.upper)]
TipoCelda = Literal["CARRO_CAMIONETA", "MOTO"]


class CeldaCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: Codigo
    tipo: TipoCelda


class CeldaActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: Codigo | None = None
    tipo: TipoCelda | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Los campos enviados no pueden ser nulos.")
        return value


class CeldaRespuesta(CeldaCrear):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int


class CeldasPagina(BaseModel):
    items: list[CeldaRespuesta]
    total: int
    offset: int
    limit: int
