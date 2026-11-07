"""Consulta con validación de mensualidad, entrada con asignación automática de celda y recibo (RF-03 a RF-05).

Concurrencia (RNF-01): la asignación bloquea la fila de la celda con FOR UPDATE SKIP LOCKED, de modo
que dos puertas que confirman a la vez reciben celdas distintas. Las restricciones de la base
(una estancia abierta por vehículo y por celda) deciden cualquier carrera restante.
"""
from datetime import datetime, timezone
from functools import wraps

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.models import TIPOS_CELDA, Celda, Estancia, Operador, Puerta, Vehiculo, tipo_celda_para
from app.schemas.celda import CeldaRespuesta
from app.schemas.cliente import ClienteRespuesta
from app.schemas.estancia import (
    ConsultaVehiculo, Cupo, EntradaCrear, MovimientoRespuesta, OperadorResumen, PuertaRespuesta, SalidaCrear,
)
from app.schemas.vehiculo import VehiculoRespuesta
from app.services.mensualidad import evaluar_mensualidad, hoy_colombia

NOMBRE_CUPO = {"CARRO_CAMIONETA": "carros y camionetas", "MOTO": "motos"}


class EstanciaError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def transaccion(operation):
    """Una transacción por solicitud; materializa la respuesta antes del commit."""
    @wraps(operation)
    def wrapped(self, *args, **kwargs):
        try:
            with self.session.begin():
                return operation(self, *args, **kwargs)
        except IntegrityError as error:
            self.session.rollback()
            code = getattr(error.orig, "sqlstate", None)
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if code == "23505" and constraint == "uq_estancia_vehiculo_abierta":
                raise EstanciaError(409, "El vehículo ya está dentro.") from None
            if code == "23505" and constraint == "uq_estancia_celda_abierta":
                raise EstanciaError(409, "La celda está ocupada. Intenta de nuevo.") from None
            if code == "23503":
                raise EstanciaError(404, "Una de las referencias ya no existe. Actualiza los datos.") from None
            if code in {"23502", "23514"}:
                raise EstanciaError(422, "Los datos incumplen las restricciones de la estancia.") from None
            raise EstanciaError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError as error:
            self.session.rollback()
            if getattr(getattr(error, "orig", None), "sqlstate", None) in {"40P01", "40001"}:
                raise EstanciaError(409, "Otra puerta modificó las mismas celdas al mismo tiempo. Intenta de nuevo.") from None
            raise EstanciaError(503, "No se pudo completar la operación con la base de datos.") from None
    return wrapped


def _abierta():
    return Estancia.salida.is_(None)


def _detalle_query():
    return select(Estancia).options(
        joinedload(Estancia.vehiculo).joinedload(Vehiculo.cliente),
        joinedload(Estancia.celda),
        joinedload(Estancia.puerta_entrada), joinedload(Estancia.puerta_salida),
        joinedload(Estancia.operador_entrada), joinedload(Estancia.operador_salida),
    )


def movimiento(estancia: Estancia) -> MovimientoRespuesta:
    vehiculo = estancia.vehiculo
    cliente = vehiculo.cliente
    return MovimientoRespuesta(
        id=estancia.id,
        numero_recibo=estancia.numero_recibo,
        vehiculo_id=vehiculo.id,
        placa=vehiculo.placa,
        tipo_vehiculo=vehiculo.tipo,
        marca=vehiculo.marca,
        linea=vehiculo.linea,
        color=vehiculo.color,
        cliente=f"{cliente.nombres} {cliente.apellidos}" if cliente else None,
        celda=CeldaRespuesta.model_validate(estancia.celda),
        entrada=estancia.entrada,
        salida=estancia.salida,
        abierta=estancia.salida is None,
        puerta_entrada=PuertaRespuesta.model_validate(estancia.puerta_entrada),
        puerta_salida=PuertaRespuesta.model_validate(estancia.puerta_salida) if estancia.puerta_salida else None,
        operador_entrada=OperadorResumen.model_validate(estancia.operador_entrada),
        operador_salida=(OperadorResumen.model_validate(estancia.operador_salida)
                         if estancia.operador_salida else None),
    )


class ServicioEstancia:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ---------- utilidades ----------

    def _operador(self, operador_id: int) -> Operador:
        operador = self.session.get(Operador, operador_id)
        if operador is None:
            raise EstanciaError(404, "Operador no encontrado.")
        return operador

    def _puerta(self, puerta_id: int) -> Puerta:
        puerta = self.session.get(Puerta, puerta_id)
        if puerta is None:
            raise EstanciaError(404, "Puerta no encontrada.")
        return puerta

    def _detalle(self, estancia_id: int) -> MovimientoRespuesta:
        self.session.expire_all()
        estancia = self.session.scalars(_detalle_query().where(Estancia.id == estancia_id)).unique().one()
        return movimiento(estancia)

    def _cupos(self) -> list[Cupo]:
        totales = dict(self.session.execute(select(Celda.tipo, func.count()).group_by(Celda.tipo)).all())
        ocupadas = dict(self.session.execute(
            select(Celda.tipo, func.count()).join(Estancia, Estancia.celda_id == Celda.id)
            .where(_abierta()).group_by(Celda.tipo)
        ).all())
        cupos = []
        for tipo in TIPOS_CELDA:
            total, ocupado = totales.get(tipo, 0), ocupadas.get(tipo, 0)
            cupos.append(Cupo(tipo_celda=tipo, nombre=NOMBRE_CUPO[tipo], total=total, ocupadas=ocupado,
                              disponibles=max(total - ocupado, 0)))
        return cupos

    def _cupo(self, tipo_celda: str) -> Cupo:
        return next(c for c in self._cupos() if c.tipo_celda == tipo_celda)

    def _celda_libre(self, tipo_celda: str) -> Celda | None:
        """RN-08: cualquier celda libre de su tipo. Se bloquea antes de confirmar que sigue libre."""
        descartadas: list[int] = []
        while True:
            ocupada = exists().where(Estancia.celda_id == Celda.id, _abierta())
            consulta = (select(Celda).where(Celda.tipo == tipo_celda, ~ocupada)
                        .order_by(Celda.codigo).limit(1).with_for_update(skip_locked=True))
            if descartadas:
                consulta = consulta.where(Celda.id.not_in(descartadas))
            celda = self.session.scalar(consulta)
            if celda is None:
                return None
            # Con la fila bloqueada, una consulta nueva ve cualquier ocupación ya confirmada.
            if self.session.scalar(select(Estancia.id).where(Estancia.celda_id == celda.id, _abierta())) is None:
                return celda
            descartadas.append(celda.id)

    # ---------- RF-03 / RF-04 ----------

    @transaccion
    def consultar(self, placa: str) -> ConsultaVehiculo:
        vehiculo = self.session.scalar(
            select(Vehiculo).options(joinedload(Vehiculo.cliente)).where(Vehiculo.placa == placa)
        )
        if vehiculo is None:
            raise EstanciaError(404, "Vehículo no registrado. Registra el cliente y el vehículo para continuar.")
        mensualidad = evaluar_mensualidad(vehiculo.cliente_id, vehiculo.fecha_pago, vehiculo.fecha_vencimiento,
                                          hoy_colombia())
        estancia = self.session.scalars(
            _detalle_query().where(Estancia.vehiculo_id == vehiculo.id, _abierta())
        ).unique().one_or_none()
        cupo = self._cupo(tipo_celda_para(vehiculo.tipo))
        motivo = None
        if estancia is not None:
            motivo = f"El vehículo ya se encuentra en la celda {estancia.celda.codigo}."
        elif not mensualidad.permite_ingreso:
            motivo = mensualidad.mensaje
        elif cupo.disponibles == 0:
            motivo = f"No hay celdas disponibles para {cupo.nombre} ({cupo.ocupadas}/{cupo.total})."
        return ConsultaVehiculo(
            vehiculo=VehiculoRespuesta.model_validate(vehiculo),
            cliente=ClienteRespuesta.model_validate(vehiculo.cliente) if vehiculo.cliente else None,
            mensualidad=mensualidad,
            esta_dentro=estancia is not None,
            estancia=movimiento(estancia) if estancia else None,
            cupo=cupo,
            puede_ingresar=motivo is None,
            motivo=motivo,
        )

    # ---------- RF-05 (con el cupo por tipo que necesita la asignación) ----------

    @transaccion
    def entrada(self, data: EntradaCrear) -> MovimientoRespuesta:
        # Bloquear el vehículo serializa dos confirmaciones del mismo vehículo en ambas puertas.
        vehiculo = self.session.scalar(select(Vehiculo).where(Vehiculo.placa == data.placa).with_for_update())
        if vehiculo is None:
            raise EstanciaError(404, "Vehículo no registrado. Registra el cliente y el vehículo para continuar.")
        operador = self._operador(data.operador_id)
        puerta = self._puerta(data.puerta_id)
        abierta = self.session.scalar(select(Estancia).where(Estancia.vehiculo_id == vehiculo.id, _abierta()))
        if abierta is not None:
            raise EstanciaError(409, f"El vehículo ya se encuentra en la celda {abierta.celda.codigo}.")
        mensualidad = evaluar_mensualidad(vehiculo.cliente_id, vehiculo.fecha_pago, vehiculo.fecha_vencimiento,
                                          hoy_colombia())
        if not mensualidad.permite_ingreso:
            raise EstanciaError(409, mensualidad.mensaje)
        tipo_celda = tipo_celda_para(vehiculo.tipo)
        celda = self._celda_libre(tipo_celda)
        if celda is None:
            cupo = self._cupo(tipo_celda)
            raise EstanciaError(
                409, f"No hay celdas disponibles para {cupo.nombre} ({cupo.ocupadas}/{cupo.total})."
            )
        estancia = Estancia(vehiculo_id=vehiculo.id, celda_id=celda.id, operador_entrada_id=operador.id,
                            puerta_entrada_id=puerta.id, entrada=datetime.now(timezone.utc))
        self.session.add(estancia)
        self.session.flush()
        return self._detalle(estancia.id)

    # ---------- Salida por placa, como antes (sus mejoras son parte de RF-07) ----------

    @transaccion
    def salida(self, data: SalidaCrear) -> MovimientoRespuesta:
        vehiculo = self.session.scalar(select(Vehiculo).where(Vehiculo.placa == data.placa))
        if vehiculo is None:
            raise EstanciaError(404, "Vehículo no registrado.")
        # PostgreSQL vuelve a evaluar salida IS NULL tras esperar el bloqueo.
        estancia = self.session.scalar(
            select(Estancia).where(Estancia.vehiculo_id == vehiculo.id, _abierta()).with_for_update()
        )
        if estancia is None:
            raise EstanciaError(409, "Este vehículo no tiene un ingreso abierto.")
        operador = self._operador(data.operador_id)
        try:
            estancia.cerrar(datetime.now(timezone.utc), operador)
        except ValueError:
            raise EstanciaError(409, "No se puede cerrar la estancia con su estado o fecha actuales.") from None
        self.session.flush()
        return self._detalle(estancia.id)

    @transaccion
    def recibo(self, numero_recibo: str) -> MovimientoRespuesta:
        estancia = self.session.scalars(
            _detalle_query().where(Estancia.numero_recibo == numero_recibo)
        ).unique().one_or_none()
        if estancia is None:
            raise EstanciaError(404, f"No existe el recibo {numero_recibo}.")
        return movimiento(estancia)
