from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.cliente import ClienteActualizar, ClienteCrear
from app.schemas.estancia import EntradaCrear, SalidaCrear, normalizar_recibo
from app.services.mensualidad import evaluar_mensualidad

HOY = date(2026, 10, 18)


def mensualidad(fecha_pago: date | None, cliente_id: int | None = 1):
    vence = fecha_pago + timedelta(days=30) if fecha_pago else None
    return evaluar_mensualidad(cliente_id, fecha_pago, vence, HOY)


def test_ejemplos_del_documento_rn06():
    # Pago el 05/10/2026 → vence el 04/11/2026; el 18/10 está vigente (HU-04, criterio 1).
    vigente = mensualidad(date(2026, 10, 5))
    assert vigente.estado == "VIGENTE" and vigente.permite_ingreso
    assert vigente.fecha_vencimiento == date(2026, 11, 4) and vigente.dias == 17
    assert vigente.mensaje == "Mensualidad vigente hasta 04/11/2026."


def test_vencida_bloquea_ingreso():
    # Venció el 15/10/2026 y llega el 18/10/2026 (HU-04, criterio 2).
    vencida = mensualidad(date(2026, 9, 15))
    assert vencida.estado == "VENCIDA" and not vencida.permite_ingreso
    assert vencida.dias == 3 and "vencida hace 3 días" in vencida.mensaje
    assert "hace 1 día " in mensualidad(date(2026, 9, 17)).mensaje


def test_vence_hoy_permite_y_avisa():
    # HU-04, criterio 3.
    hoy = mensualidad(HOY - timedelta(days=30))
    assert hoy.estado == "VENCE_HOY" and hoy.permite_ingreso and "vence hoy" in hoy.mensaje


@pytest.mark.parametrize("cliente_id, fecha_pago, estado", [(None, date(2026, 10, 5), "SIN_CLIENTE"),
                                                            (1, None, "SIN_PAGO")])
def test_vehiculo_sin_cliente_o_sin_pago_no_ingresa(cliente_id, fecha_pago, estado):
    resultado = mensualidad(fecha_pago, cliente_id)
    assert resultado.estado == estado and not resultado.permite_ingreso


@pytest.mark.parametrize("valor, esperado", [("E-000245", "E-000245"), ("e000245", "E-000245"), (" 245 ", "E-000245"),
                                             ("E-1234567", "E-1234567")])
def test_recibo_se_normaliza(valor, esperado):
    assert normalizar_recibo(valor) == esperado


@pytest.mark.parametrize("valor", ["", "E-", "ABC", "E-0", "0", "E-12A"])
def test_recibo_invalido(valor):
    with pytest.raises(ValueError):
        normalizar_recibo(valor)


def test_entrada_no_acepta_celda_y_exige_puerta():
    # RF-05: la celda la asigna el sistema y se registra la puerta.
    with pytest.raises(ValidationError):
        EntradaCrear(placa="ABC123", operador_id=1, puerta_id=1, celda_id=1)
    with pytest.raises(ValidationError):
        EntradaCrear(placa="ABC123", operador_id=1)
    # La salida conserva su contrato: placa y operador.
    assert SalidaCrear(placa="abc-123", operador_id=1).placa == "ABC123"


def test_cliente_normaliza_documento_telefono_y_correo():
    cliente = ClienteCrear(tipo_documento="CC", numero_documento="1.036.458.221", nombres=" Laura ",
                           apellidos="Gómez", telefono="+57 300 123 4567", correo=" Laura@Correo.COM ")
    assert cliente.numero_documento == "1036458221"
    assert cliente.telefono == "3001234567"
    assert cliente.correo == "laura@correo.com"
    assert cliente.nombres == "Laura"
    assert ClienteCrear(tipo_documento="CE", numero_documento="AB123", nombres="A", apellidos="B",
                        telefono="6011234567", correo="").correo is None


@pytest.mark.parametrize("campo, valor", [("tipo_documento", "DNI"), ("numero_documento", "12"),
                                          ("telefono", "12345"), ("correo", "sin-arroba"), ("nombres", " ")])
def test_cliente_invalido(campo, valor):
    datos = {"tipo_documento": "CC", "numero_documento": "1036458221", "nombres": "Laura", "apellidos": "Gómez",
             "telefono": "3001234567", "correo": None, campo: valor}
    with pytest.raises(ValidationError):
        ClienteCrear(**datos)


def test_actualizar_cliente_rechaza_nulos_salvo_correo():
    with pytest.raises(ValidationError):
        ClienteActualizar(nombres=None)
    assert ClienteActualizar(correo=None).model_dump(exclude_unset=True) == {"correo": None}
