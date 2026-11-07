"""Vigencia de la mensualidad (RN-06, RN-07, RF-04). Sin acceso a base de datos."""

from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

ZONA_COLOMBIA = ZoneInfo("America/Bogota")

EstadoMensualidad = Literal["VIGENTE", "VENCE_HOY", "VENCIDA", "SIN_PAGO", "SIN_CLIENTE"]


class Mensualidad(BaseModel):
    estado: EstadoMensualidad
    fecha_pago: date | None
    fecha_vencimiento: date | None
    dias: int | None
    """Días que faltan (vigente) o que han pasado desde el vencimiento (vencida)."""
    permite_ingreso: bool
    mensaje: str


def hoy_colombia() -> date:
    """RNF-11: la fecha la decide el servidor en la zona horaria de Colombia."""
    return datetime.now(ZONA_COLOMBIA).date()


def _fecha(valor: date) -> str:
    return valor.strftime("%d/%m/%Y")


def evaluar_mensualidad(
    cliente_id: int | None, fecha_pago: date | None, fecha_vencimiento: date | None, hoy: date
) -> Mensualidad:
    if cliente_id is None:
        return Mensualidad(
            estado="SIN_CLIENTE", fecha_pago=fecha_pago, fecha_vencimiento=fecha_vencimiento, dias=None,
            permite_ingreso=False,
            mensaje="El vehículo no está asociado a un cliente. Asócialo antes de registrar el ingreso.",
        )
    if fecha_pago is None or fecha_vencimiento is None:
        return Mensualidad(
            estado="SIN_PAGO", fecha_pago=None, fecha_vencimiento=None, dias=None, permite_ingreso=False,
            mensaje="El vehículo no tiene una mensualidad registrada. Registra la fecha de pago.",
        )
    dias = (fecha_vencimiento - hoy).days
    if dias > 0:
        return Mensualidad(
            estado="VIGENTE", fecha_pago=fecha_pago, fecha_vencimiento=fecha_vencimiento, dias=dias,
            permite_ingreso=True, mensaje=f"Mensualidad vigente hasta {_fecha(fecha_vencimiento)}.",
        )
    if dias == 0:
        return Mensualidad(
            estado="VENCE_HOY", fecha_pago=fecha_pago, fecha_vencimiento=fecha_vencimiento, dias=0,
            permite_ingreso=True, mensaje="La mensualidad vence hoy. Recuerda al cliente renovarla.",
        )
    vencidos = -dias
    return Mensualidad(
        estado="VENCIDA", fecha_pago=fecha_pago, fecha_vencimiento=fecha_vencimiento, dias=vencidos,
        permite_ingreso=False,
        mensaje=f"Mensualidad vencida hace {vencidos} {'día' if vencidos == 1 else 'días'} "
                f"(venció el {_fecha(fecha_vencimiento)}). No se permite el ingreso.",
    )
